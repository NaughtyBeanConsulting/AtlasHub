import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import space_required
from core.models import Space, SpaceMembership

from .models import EPIC_COLORS, Issue, Sprint, Status
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
    """A project's default view: the board while a sprint runs, else backlog."""
    if space.sprints.filter(state=Sprint.STATE_ACTIVE).exists():
        return redirect('projects:board', key=space.key)
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


def _open_sprints(space):
    """Active + planned sprints with their (non-subtask) issues, for the
    backlog's sprint-planning panels."""
    sprints = list(
        space.sprints
        .filter(state__in=[Sprint.STATE_ACTIVE, Sprint.STATE_PLANNED])
        .order_by('-state', 'created_at')  # active first
    )
    issues = (
        space.issues.filter(sprint__in=sprints)
        .exclude(issue_type=Issue.TYPE_SUBTASK)
        .select_related('status', 'assignee', 'epic')
    )
    by_sprint = {}
    for issue in issues:
        by_sprint.setdefault(issue.sprint_id, []).append(issue)
    return [{'sprint': s, 'issues': by_sprint.get(s.id, [])} for s in sprints]


@space_required(space_type=Space.TYPE_SOFTWARE)
def backlog(request, space):
    today = timezone.localdate()
    return render(request, 'projects/backlog.html', {
        'space': space,
        'groups': _backlog_groups(space),
        'sprint_groups': (sprint_groups := _open_sprints(space)),
        'planned_sprints': [g['sprint'] for g in sprint_groups
                            if g['sprint'].state == Sprint.STATE_PLANNED],
        'has_active_sprint': any(g['sprint'].state == Sprint.STATE_ACTIVE for g in sprint_groups),
        'creatable_types': [c for c in Issue.TYPE_CHOICES if c[0] in Issue.STANDARD_TYPES],
        'epic_colors': EPIC_COLORS,
        'default_start': today,
        'default_end': today + datetime.timedelta(days=14),
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

    # The moved issue may be arriving from a sprint panel, so don't filter on
    # sprint here — membership of the space is the trust boundary.
    issues = {i.pk: i for i in space.issues.filter(pk__in=ids)}
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
        if str(pk) == moved_id:
            if issue.epic_id != (epic.pk if epic else None):
                record_activity(
                    issue, request.user, 'epic',
                    issue.epic.summary if issue.epic else '',
                    epic.summary if epic else '',
                )
                issue.epic = epic
                if issue not in to_update:
                    to_update.append(issue)
            if issue.sprint_id is not None:
                record_activity(issue, request.user, 'sprint', issue.sprint.name, 'Backlog')
                issue.sprint = None
                if issue not in to_update:
                    to_update.append(issue)
    Issue.objects.bulk_update(to_update, ['rank', 'epic', 'sprint'])
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


# ── Sprints ──────────────────────────────────────────────────────────────────

@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def sprint_create(request, space):
    name = request.POST.get('name', '').strip() or f'{space.key} Sprint {space.sprints.count() + 1}'
    Sprint.objects.create(space=space, name=name)
    messages.success(request, f'Sprint “{name}” created — drag issues into it, then start it.')
    return redirect('projects:backlog', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def sprint_move(request, space):
    """Drop handler for the backlog's sprint panels: assign the moved issue to
    the sprint and re-rank the panel's list."""
    sprint = get_object_or_404(
        Sprint, pk=request.POST.get('sprint'), space=space,
        state__in=[Sprint.STATE_ACTIVE, Sprint.STATE_PLANNED],
    )
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    moved_id = request.POST.get('moved')
    issues = {i.pk: i for i in space.issues.filter(pk__in=ids)}
    if len(issues) != len(ids):
        return HttpResponseBadRequest('Stale backlog — reload the page.')

    to_update = []
    for index, pk in enumerate(int(i) for i in ids):
        issue = issues[pk]
        if issue.rank != index:
            issue.rank = index
            to_update.append(issue)
        if str(pk) == moved_id and issue.sprint_id != sprint.pk:
            record_activity(
                issue, request.user, 'sprint',
                issue.sprint.name if issue.sprint else 'Backlog', sprint.name,
            )
            issue.sprint = sprint
            if issue not in to_update:
                to_update.append(issue)
    Issue.objects.bulk_update(to_update, ['rank', 'sprint'])
    return HttpResponse(status=204)


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def sprint_start(request, space, sprint_id):
    sprint = get_object_or_404(Sprint, pk=sprint_id, space=space, state=Sprint.STATE_PLANNED)
    if space.sprints.filter(state=Sprint.STATE_ACTIVE).exists():
        messages.error(request, 'Another sprint is already active — complete it first.')
        return redirect('projects:backlog', key=space.key)

    name = request.POST.get('name', '').strip() or sprint.name
    goal = request.POST.get('goal', '').strip()
    try:
        start_date = datetime.date.fromisoformat(request.POST.get('start_date', ''))
        end_date = datetime.date.fromisoformat(request.POST.get('end_date', ''))
    except ValueError:
        messages.error(request, 'Start and end dates are required to start a sprint.')
        return redirect('projects:backlog', key=space.key)
    if end_date <= start_date:
        messages.error(request, 'The sprint must end after it starts.')
        return redirect('projects:backlog', key=space.key)

    sprint.name, sprint.goal = name, goal
    sprint.start_date, sprint.end_date = start_date, end_date
    sprint.state = Sprint.STATE_ACTIVE
    sprint.save()
    messages.success(request, f'Sprint “{sprint.name}” started.')
    return redirect('projects:board', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def sprint_complete(request, space, sprint_id):
    sprint = get_object_or_404(Sprint, pk=sprint_id, space=space, state=Sprint.STATE_ACTIVE)
    incomplete = list(
        sprint.issues.exclude(status__category=Status.CATEGORY_DONE)
        .select_related('status')
    )

    target = request.POST.get('target', 'backlog')
    target_sprint = None
    if target != 'backlog':
        target_sprint = get_object_or_404(
            Sprint, pk=target, space=space, state=Sprint.STATE_PLANNED,
        )

    for issue in incomplete:
        record_activity(
            issue, request.user, 'sprint', sprint.name,
            target_sprint.name if target_sprint else 'Backlog',
        )
        issue.sprint = target_sprint
    Issue.objects.bulk_update(incomplete, ['sprint'])

    sprint.state = Sprint.STATE_COMPLETED
    sprint.completed_at = timezone.now()
    sprint.save(update_fields=['state', 'completed_at'])

    done_count = sprint.issues.count()
    destination = f'moved to “{target_sprint.name}”' if target_sprint else 'returned to the backlog'
    messages.success(
        request,
        f'Sprint “{sprint.name}” completed — {done_count} done, {len(incomplete)} {destination}.',
    )
    return redirect('projects:backlog', key=space.key)


# ── Board ────────────────────────────────────────────────────────────────────

@space_required(space_type=Space.TYPE_SOFTWARE)
def board(request, space):
    sprint = space.sprints.filter(state=Sprint.STATE_ACTIVE).first()
    statuses = list(space.statuses.all())
    columns = []
    if sprint:
        issues = (
            sprint.issues.exclude(issue_type=Issue.TYPE_SUBTASK)
            .select_related('status', 'assignee', 'epic')
        )
        by_status = {}
        for issue in issues:
            by_status.setdefault(issue.status_id, []).append(issue)
        columns = [{'status': s, 'issues': by_status.get(s.id, [])} for s in statuses]

    days_left = None
    if sprint and sprint.end_date:
        days_left = (sprint.end_date - timezone.localdate()).days

    return render(request, 'projects/board.html', {
        'space': space,
        'sprint': sprint,
        'columns': columns,
        'days_left': days_left,
        'planned_sprints': space.sprints.filter(state=Sprint.STATE_PLANNED),
    })


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def board_move(request, space):
    status = get_object_or_404(Status, pk=request.POST.get('status'), space=space)
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    moved_id = request.POST.get('moved')
    issues = {i.pk: i for i in space.issues.filter(pk__in=ids).select_related('status')}
    if len(issues) != len(ids):
        return HttpResponseBadRequest('Stale board — reload the page.')

    to_update = []
    for index, pk in enumerate(int(i) for i in ids):
        issue = issues[pk]
        if issue.rank != index:
            issue.rank = index
            to_update.append(issue)
        if str(pk) == moved_id and issue.status_id != status.pk:
            record_activity(issue, request.user, 'status', issue.status.name, status.name)
            issue.status = status
            if issue not in to_update:
                to_update.append(issue)
    Issue.objects.bulk_update(to_update, ['rank', 'status'])
    return HttpResponse(status=204)


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
