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

from .models import (
    EPIC_COLORS, AcceptanceCriterion, Activity, Comment, Issue, Label, Sprint,
    Status,
)
from .notifications import notify_issue_assigned, notify_mentions, notify_sprint_event
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
    return render(request, 'projects/partials/backlog_row.html', {
        'issue': issue,
        'space': space,
        'has_active_sprint': space.sprints.filter(state=Sprint.STATE_ACTIVE).exists(),
    })


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
    notify_sprint_event(sprint, request.user, 'started')
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
    notify_sprint_event(sprint, request.user, 'completed')

    done_count = sprint.issues.count()
    destination = f'moved to “{target_sprint.name}”' if target_sprint else 'returned to the backlog'
    messages.success(
        request,
        f'Sprint “{sprint.name}” completed — {done_count} done, {len(incomplete)} {destination}.',
    )
    return redirect('projects:backlog', key=space.key)


@space_required(space_type=Space.TYPE_SOFTWARE)
def sprints(request, space):
    """Sprint history: every sprint (active, planned, completed) with its
    issues and done/points stats. Completed sprints keep their finished
    issues; incomplete ones were moved out at completion, so the carried-over
    count is reconstructed from the activity log."""
    state_order = {Sprint.STATE_ACTIVE: 0, Sprint.STATE_PLANNED: 1, Sprint.STATE_COMPLETED: 2}
    all_sprints = sorted(
        space.sprints.all(),
        key=lambda s: (state_order[s.state], -(s.completed_at or s.created_at).timestamp()),
    )
    issues = (
        space.issues.filter(sprint__in=all_sprints)
        .exclude(issue_type=Issue.TYPE_SUBTASK)
        .select_related('status', 'assignee', 'epic')
    )
    by_sprint = {}
    for issue in issues:
        by_sprint.setdefault(issue.sprint_id, []).append(issue)

    carried = {
        row['old_value']: row['n'] for row in
        Activity.objects.filter(issue__space=space, field='sprint')
        .exclude(old_value='')
        .values('old_value')
        .annotate(n=Count('issue', distinct=True))
    }

    groups = []
    for sprint in all_sprints:
        sprint_issues = by_sprint.get(sprint.pk, [])
        done = [i for i in sprint_issues if i.is_done]
        groups.append({
            'sprint': sprint,
            'issues': sprint_issues,
            'done_count': len(done),
            'points_total': sum(i.story_points or 0 for i in sprint_issues),
            'points_done': sum(i.story_points or 0 for i in done),
            'carried_over': carried.get(sprint.name, 0) if sprint.state == Sprint.STATE_COMPLETED else 0,
        })
    return render(request, 'projects/sprints.html', {'space': space, 'groups': groups})


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_SOFTWARE)
def sprint_quick_add(request, space):
    """One-click 'pull into the active sprint' from a backlog row."""
    sprint = space.sprints.filter(state=Sprint.STATE_ACTIVE).first()
    if sprint is None:
        return HttpResponseBadRequest('No active sprint.')
    issue = get_object_or_404(
        Issue, pk=request.POST.get('issue'), space=space, sprint__isnull=True,
    )
    issue.sprint = sprint
    issue.rank = _next_rank(sprint.issues.all())
    issue.save(update_fields=['sprint', 'rank', 'updated_at'])
    record_activity(issue, request.user, 'sprint', 'Backlog', sprint.name)
    # Both the backlog groups and the sprint panel change — reload the page.
    response = HttpResponse(status=204)
    response['HX-Refresh'] = 'true'
    return response


# ── Board columns (lanes) ────────────────────────────────────────────────────

@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def board_columns(request, space):
    statuses = space.statuses.annotate(issue_count=Count('issues'))
    return render(request, 'projects/board_columns.html', {
        'space': space,
        'statuses': statuses,
        'categories': Status.CATEGORY_CHOICES,
    })


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def column_add(request, space):
    name = request.POST.get('name', '').strip()
    category = request.POST.get('category', Status.CATEGORY_TODO)
    if category not in dict(Status.CATEGORY_CHOICES):
        category = Status.CATEGORY_TODO
    if not name:
        messages.error(request, 'Columns need a name.')
    elif space.statuses.filter(name__iexact=name).exists():
        messages.error(request, f'A “{name}” column already exists.')
    else:
        order = (space.statuses.aggregate(m=Max('order'))['m'] or 0) + 1
        Status.objects.create(space=space, name=name, category=category, order=order)
        messages.success(request, f'Column “{name}” added.')
    return redirect('projects:board_columns', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def column_update(request, space, status_id):
    status = get_object_or_404(Status, pk=status_id, space=space)
    name = request.POST.get('name', '').strip()
    category = request.POST.get('category', status.category)
    if not name:
        messages.error(request, 'Columns need a name.')
    elif space.statuses.exclude(pk=status.pk).filter(name__iexact=name).exists():
        messages.error(request, f'A “{name}” column already exists.')
    else:
        status.name = name
        if category in dict(Status.CATEGORY_CHOICES):
            status.category = category
        status.save(update_fields=['name', 'category'])
        messages.success(request, 'Column updated.')
    return redirect('projects:board_columns', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def column_delete(request, space, status_id):
    status = get_object_or_404(Status, pk=status_id, space=space)
    if space.statuses.count() <= 1:
        messages.error(request, 'A board needs at least one column.')
        return redirect('projects:board_columns', key=space.key)

    target = None
    if status.issues.exists():
        target = space.statuses.exclude(pk=status.pk).filter(
            pk=request.POST.get('move_to'),
        ).first()
        if target is None:
            messages.error(request, 'Choose a column to move its issues to first.')
            return redirect('projects:board_columns', key=space.key)
        moved = status.issues.update(status=target)
        messages.success(
            request, f'“{status.name}” deleted — {moved} issue(s) moved to “{target.name}”.',
        )
    else:
        messages.success(request, f'“{status.name}” deleted.')
    status.delete()
    return redirect('projects:board_columns', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_ADMIN, space_type=Space.TYPE_SOFTWARE)
def columns_reorder(request, space):
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    statuses = {s.pk: s for s in space.statuses.filter(pk__in=ids)}
    if len(statuses) != len(ids):
        return HttpResponseBadRequest('Stale column list — reload the page.')
    to_update = []
    for index, pk in enumerate(int(i) for i in ids):
        if statuses[pk].order != index:
            statuses[pk].order = index
            to_update.append(statuses[pk])
    Status.objects.bulk_update(to_update, ['order'])
    return HttpResponse(status=204)


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


# ── Issue detail ─────────────────────────────────────────────────────────────

def _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_VIEWER):
    issue = get_object_or_404(
        Issue.objects.select_related('space', 'status', 'assignee', 'reporter', 'epic', 'sprint', 'parent'),
        key__iexact=issue_key,
    )
    role = issue.space.role_for(request.user)
    if role is None:
        raise Http404
    if SpaceMembership.ROLE_RANK[role] < SpaceMembership.ROLE_RANK[min_role]:
        raise Http404
    request.space, request.space_role = issue.space, role
    return issue


def _detail_context(request, issue, layout='page'):
    space = issue.space
    return {
        'issue': issue,
        'space': space,
        'layout': layout,
        'can_edit': SpaceMembership.ROLE_RANK[request.space_role] >= SpaceMembership.ROLE_RANK[SpaceMembership.ROLE_MEMBER],
        'statuses': space.statuses.all(),
        'members': space.members.filter(is_active=True),
        'open_sprints': space.sprints.filter(state__in=[Sprint.STATE_PLANNED, Sprint.STATE_ACTIVE]),
        'epics': space.issues.filter(issue_type=Issue.TYPE_EPIC).exclude(pk=issue.pk),
        'priorities': Issue.PRIORITY_CHOICES,
        'subtasks': issue.subtasks.select_related('status', 'assignee'),
        'criteria': issue.acceptance_criteria.all(),
        'comments': issue.comments.select_related('author'),
        'label_names': ', '.join(issue.labels.values_list('name', flat=True)),
        'epic_children': (
            issue.epic_issues.select_related('status', 'assignee')
            if issue.issue_type == Issue.TYPE_EPIC else None
        ),
    }


@login_required
def issue_browse(request, issue_key):
    issue = _get_issue(request, issue_key)
    return render(request, 'projects/issue_browse.html', _detail_context(request, issue))


@login_required
def issue_panel(request, issue_key):
    """The same detail, as a side-panel partial over the board/backlog."""
    issue = _get_issue(request, issue_key)
    return render(request, 'projects/partials/issue_panel.html',
                  _detail_context(request, issue, layout='panel'))


@require_POST
@login_required
def issue_field(request, issue_key, field):
    """Inline edit of a single issue field; responds with that field's block."""
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    space = issue.space
    value = request.POST.get('value', '').strip()

    if field == 'summary':
        if value:
            record_activity(issue, request.user, 'summary', issue.summary, value)
            issue.summary = value
            issue.save(update_fields=['summary', 'updated_at'])
    elif field == 'description':
        issue.description_md = request.POST.get('value', '')
        record_activity(issue, request.user, 'description', '', 'updated')
        issue.save(update_fields=['description_md', 'updated_at'])
        notify_mentions(issue, request.user, issue.description_md)
    elif field == 'status':
        status = get_object_or_404(Status, pk=value, space=space)
        if status.pk != issue.status_id:
            record_activity(issue, request.user, 'status', issue.status.name, status.name)
            issue.status = status
            issue.save(update_fields=['status', 'updated_at'])
    elif field == 'priority':
        if value in dict(Issue.PRIORITY_CHOICES) and value != issue.priority:
            record_activity(issue, request.user, 'priority',
                            issue.get_priority_display(), dict(Issue.PRIORITY_CHOICES)[value])
            issue.priority = value
            issue.save(update_fields=['priority', 'updated_at'])
    elif field == 'story_points':
        try:
            points = None if value == '' else max(0, min(999, int(value)))
        except ValueError:
            points = issue.story_points
        if points != issue.story_points:
            record_activity(issue, request.user, 'story points',
                            issue.story_points or '', points if points is not None else '')
            issue.story_points = points
            issue.save(update_fields=['story_points', 'updated_at'])
    elif field == 'assignee':
        assignee = space.members.filter(pk=value).first() if value else None
        if (assignee.pk if assignee else None) != issue.assignee_id:
            record_activity(issue, request.user, 'assignee',
                            issue.assignee.display_name if issue.assignee else 'Unassigned',
                            assignee.display_name if assignee else 'Unassigned')
            old_assignee = issue.assignee
            issue.assignee = assignee
            issue.save(update_fields=['assignee', 'updated_at'])
            notify_issue_assigned(issue, request.user, old_assignee)
    elif field == 'sprint':
        if value and str(issue.sprint_id) == value:
            # Re-selected the current sprint (possibly a completed one that
            # isn't in the open-sprint options) — nothing to change.
            sprint = issue.sprint
        else:
            sprint = get_object_or_404(
                Sprint, pk=value, space=space,
                state__in=[Sprint.STATE_PLANNED, Sprint.STATE_ACTIVE],
            ) if value else None
        if (sprint.pk if sprint else None) != issue.sprint_id:
            record_activity(issue, request.user, 'sprint',
                            issue.sprint.name if issue.sprint else 'Backlog',
                            sprint.name if sprint else 'Backlog')
            issue.sprint = sprint
            issue.save(update_fields=['sprint', 'updated_at'])
    elif field == 'epic':
        epic = get_object_or_404(
            Issue, pk=value, space=space, issue_type=Issue.TYPE_EPIC,
        ) if value else None
        if issue.issue_type != Issue.TYPE_EPIC and (epic.pk if epic else None) != issue.epic_id:
            record_activity(issue, request.user, 'epic',
                            issue.epic.summary if issue.epic else '',
                            epic.summary if epic else '')
            issue.epic = epic
            issue.save(update_fields=['epic', 'updated_at'])
    elif field == 'labels':
        names = [n.strip() for n in value.split(',') if n.strip()][:10]
        labels = [Label.objects.get_or_create(space=space, name=name)[0] for name in names]
        old = ', '.join(issue.labels.values_list('name', flat=True))
        new = ', '.join(label.name for label in labels)
        if old != new:
            record_activity(issue, request.user, 'labels', old, new)
            issue.labels.set(labels)
    else:
        return HttpResponseBadRequest('Unknown field.')

    context = _detail_context(request, issue, layout=request.POST.get('layout', 'page'))
    if field == 'summary':
        return render(request, 'projects/partials/detail_summary.html', context)
    if field == 'description':
        return render(request, 'projects/partials/detail_description.html', context)
    context['field'] = field
    return render(request, 'projects/partials/detail_field.html', context)


@require_POST
@login_required
def comment_add(request, issue_key):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    body = request.POST.get('body_md', '').strip()
    if body:
        comment = Comment.objects.create(issue=issue, author=request.user, body_md=body)
        notify_mentions(issue, request.user, body)
        record_activity(issue, request.user, 'comment', '', f'#{comment.pk}')
    return render(request, 'projects/partials/comments.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@require_POST
@login_required
def comment_delete(request, issue_key, comment_id):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    comment = get_object_or_404(Comment, pk=comment_id, issue=issue)
    if comment.author_id == request.user.id or request.space_role == SpaceMembership.ROLE_ADMIN:
        comment.delete()
    return render(request, 'projects/partials/comments.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@require_POST
@login_required
def ac_add(request, issue_key):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    text = request.POST.get('text', '').strip()
    if text:
        order = (issue.acceptance_criteria.aggregate(m=Max('order'))['m'] or 0) + 1
        AcceptanceCriterion.objects.create(issue=issue, text=text, order=order)
    return render(request, 'projects/partials/ac_list.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@require_POST
@login_required
def ac_toggle(request, issue_key, ac_id):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    criterion = get_object_or_404(AcceptanceCriterion, pk=ac_id, issue=issue)
    criterion.is_done = not criterion.is_done
    criterion.save(update_fields=['is_done'])
    return render(request, 'projects/partials/ac_list.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@require_POST
@login_required
def ac_delete(request, issue_key, ac_id):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    get_object_or_404(AcceptanceCriterion, pk=ac_id, issue=issue).delete()
    return render(request, 'projects/partials/ac_list.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@require_POST
@login_required
def subtask_add(request, issue_key):
    issue = _get_issue(request, issue_key, min_role=SpaceMembership.ROLE_MEMBER)
    summary = request.POST.get('summary', '').strip()
    if summary and issue.issue_type != Issue.TYPE_SUBTASK:
        subtask = Issue.objects.create_issue(
            space=issue.space,
            issue_type=Issue.TYPE_SUBTASK,
            summary=summary,
            status=_first_status(issue.space),
            reporter=request.user,
            parent=issue,
            epic=issue.epic,
        )
        record_activity(subtask, request.user, 'created')
        record_activity(issue, request.user, 'subtask', '', subtask.key)
    return render(request, 'projects/partials/subtask_list.html',
                  _detail_context(request, issue, layout=request.POST.get('layout', 'page')))


@login_required
def issue_activity(request, issue_key):
    issue = _get_issue(request, issue_key)
    return render(request, 'projects/partials/activity_list.html', {
        'activities': issue.activities.select_related('actor')[:50],
    })


# ── Timeline ─────────────────────────────────────────────────────────────────

@space_required(space_type=Space.TYPE_SOFTWARE)
def timeline(request, space):
    sprints = list(
        space.sprints
        .exclude(start_date__isnull=True).exclude(end_date__isnull=True)
        .order_by('start_date')
    )
    context = {'space': space, 'sprints': sprints}
    if sprints:
        range_start = min(s.start_date for s in sprints)
        range_start -= datetime.timedelta(days=range_start.weekday())  # snap to Monday
        range_end = max(s.end_date for s in sprints)
        range_end += datetime.timedelta(days=6 - range_end.weekday())  # snap to Sunday
        total_days = (range_end - range_start).days + 1

        def col(day):
            return (day - range_start).days + 1  # css grid columns are 1-based

        sprint_bars = [{
            'sprint': s,
            'start': col(s.start_date),
            'span': (s.end_date - s.start_date).days + 1,
        } for s in sprints]

        # An epic spans from the start of the earliest sprint containing its
        # issues to the end of the latest one. Each of those issues also gets
        # its own bar (spanning its sprint) for the expanded view.
        dated = {s.pk: s for s in sprints}
        epic_bars = []
        epic_sprints = {}
        epic_issue_bars = {}
        issues_in_sprints = (
            space.issues.filter(epic__isnull=False, sprint__in=sprints)
            .exclude(issue_type=Issue.TYPE_SUBTASK)
            .select_related('epic', 'sprint', 'status', 'assignee')
        )
        for issue in issues_in_sprints:
            sprint = dated[issue.sprint_id]
            epic_sprints.setdefault(issue.epic, []).append(sprint)
            epic_issue_bars.setdefault(issue.epic, []).append({
                'issue': issue,
                'start': col(sprint.start_date),
                'span': (sprint.end_date - sprint.start_date).days + 1,
            })
        for epic in space.issues.filter(issue_type=Issue.TYPE_EPIC):
            in_sprints = epic_sprints.get(epic)
            if not in_sprints:
                continue
            start = min(s.start_date for s in in_sprints)
            end = max(s.end_date for s in in_sprints)
            epic_bars.append({
                'epic': epic,
                'start': col(start),
                'span': (end - start).days + 1,
                'issues': epic_issue_bars.get(epic, []),
            })

        today = timezone.localdate()
        weeks = [range_start + datetime.timedelta(days=7 * i) for i in range(total_days // 7)]
        context.update({
            'total_days': total_days,
            'weeks': weeks,
            'sprint_bars': sprint_bars,
            'epic_bars': epic_bars,
            'unscheduled_epics': [
                e for e in space.issues.filter(issue_type=Issue.TYPE_EPIC)
                if e not in epic_sprints
            ],
            'today_pct': (
                round(((today - range_start).days + 0.5) / total_days * 100, 2)
                if range_start <= today <= range_end else None
            ),
        })
    return render(request, 'projects/timeline.html', context)
