from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import space_required
from core.models import Space, SpaceMembership

from .models import EPIC_COLORS, Issue, Status
from .services import record_activity


@login_required
def home(request):
    spaces = (
        request.user.spaces
        .filter(space_type=Space.TYPE_SOFTWARE)
        .annotate(issue_count=Count('issues'))
    )
    return render(request, 'projects/home.html', {'spaces': spaces})


@space_required(space_type=Space.TYPE_SOFTWARE)
def project_home(request, space):
    """A project's default view (the board once a sprint exists, else backlog)."""
    return redirect('projects:backlog', key=space.key)


def _backlog_groups(space):
    """Unscheduled issues grouped by epic (epics in rank order, 'No epic' last)."""
    epics = list(space.issues.filter(issue_type=Issue.TYPE_EPIC))
    issues = (
        space.issues.filter(sprint__isnull=True)
        .exclude(issue_type__in=[Issue.TYPE_EPIC, Issue.TYPE_SUBTASK])
        .select_related('status', 'assignee', 'epic')
    )
    by_epic = {}
    for issue in issues:
        by_epic.setdefault(issue.epic_id, []).append(issue)
    groups = [{'epic': epic, 'issues': by_epic.get(epic.id, [])} for epic in epics]
    groups.append({'epic': None, 'issues': by_epic.get(None, [])})
    return groups


@space_required(space_type=Space.TYPE_SOFTWARE)
def backlog(request, space):
    return render(request, 'projects/backlog.html', {
        'space': space,
        'groups': _backlog_groups(space),
        'creatable_types': [c for c in Issue.TYPE_CHOICES if c[0] in Issue.STANDARD_TYPES],
        'epic_colors': EPIC_COLORS,
    })


def _first_status(space):
    status = space.statuses.first()
    if status is None:
        # Defensive: spaces created before seeding existed.
        status = Status.objects.create(space=space, name='To Do', category=Status.CATEGORY_TODO)
    return status


def _next_rank(queryset):
    return (queryset.aggregate(m=Max('rank'))['m'] or 0) + 1


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def issue_create_inline(request, space):
    issue_type = request.POST.get('issue_type', Issue.TYPE_STORY)
    summary = request.POST.get('summary', '').strip()
    if issue_type not in Issue.STANDARD_TYPES or not summary:
        return HttpResponseBadRequest('A summary and a valid type are required.')

    epic = None
    if request.POST.get('epic'):
        epic = get_object_or_404(
            Issue, pk=request.POST['epic'], space=space, issue_type=Issue.TYPE_EPIC,
        )

    issue = Issue.objects.create_issue(
        space=space,
        issue_type=issue_type,
        summary=summary,
        status=_first_status(space),
        reporter=request.user,
        epic=epic,
        rank=_next_rank(space.issues.filter(sprint__isnull=True, epic=epic)),
    )
    record_activity(issue, request.user, 'created')
    return render(request, 'projects/partials/backlog_row.html', {'issue': issue, 'space': space})


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def backlog_reorder(request, space):
    """SortableJS drop handler: re-rank one epic group; the moved issue may
    also have been dragged into a different epic group."""
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    moved_id = request.POST.get('moved')
    epic_id = request.POST.get('epic') or None

    issues = {i.pk: i for i in space.issues.filter(pk__in=ids, sprint__isnull=True)}
    if len(issues) != len(ids):
        return HttpResponseBadRequest('Stale backlog — reload the page.')

    epic = None
    if epic_id:
        epic = get_object_or_404(Issue, pk=epic_id, space=space, issue_type=Issue.TYPE_EPIC)

    to_update = []
    for index, pk in enumerate(int(i) for i in ids):
        issue = issues[pk]
        if issue.rank != index:
            issue.rank = index
            to_update.append(issue)
        if str(pk) == moved_id and issue.epic_id != (epic.pk if epic else None):
            record_activity(
                issue, request.user, 'epic',
                issue.epic.summary if issue.epic else '',
                epic.summary if epic else '',
            )
            issue.epic = epic
            if issue not in to_update:
                to_update.append(issue)
    Issue.objects.bulk_update(to_update, ['rank', 'epic'])
    return HttpResponse(status=204)


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def epic_create(request, space):
    summary = request.POST.get('summary', '').strip()
    color = request.POST.get('color', EPIC_COLORS[0])
    if not summary:
        messages.error(request, 'Epics need a name.')
        return redirect('projects:backlog', key=space.key)
    if color not in EPIC_COLORS:
        color = EPIC_COLORS[0]
    epic = Issue.objects.create_issue(
        space=space,
        issue_type=Issue.TYPE_EPIC,
        summary=summary,
        status=_first_status(space),
        reporter=request.user,
        epic_color=color,
        rank=_next_rank(space.issues.filter(issue_type=Issue.TYPE_EPIC)),
    )
    record_activity(epic, request.user, 'created')
    messages.success(request, f'Epic {epic.key} created.')
    return redirect('projects:backlog', key=space.key)


@login_required
def issue_browse(request, issue_key):
    issue = get_object_or_404(
        Issue.objects.select_related('space', 'status', 'assignee', 'reporter', 'epic', 'sprint'),
        key__iexact=issue_key,
    )
    if issue.space.role_for(request.user) is None:
        raise Http404
    return render(request, 'projects/issue_browse.html', {
        'issue': issue,
        'space': issue.space,
    })
