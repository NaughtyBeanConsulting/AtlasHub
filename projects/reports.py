"""Sprint analytics: capacity planning, burndown and velocity series.

Chart functions return SVG-ready geometry (polyline point strings, bar
rectangles) so templates stay dumb and no JS chart library is needed.
"""
import datetime

from django.db.models import Sum
from django.utils import timezone

from .models import Activity, Issue, Sprint, SprintCapacity

CHART_W, CHART_H, PAD = 560, 180, 28


def working_days(start, end):
    """Weekdays between two dates, inclusive."""
    days, day = 0, start
    while day <= end:
        if day.weekday() < 5:
            days += 1
        day += datetime.timedelta(days=1)
    return max(days, 1)


def sprint_issue_qs(sprint):
    return sprint.issues.exclude(issue_type=Issue.TYPE_SUBTASK).filter(archived=False)


# ── Capacity ─────────────────────────────────────────────────────────────────

def capacity_overview(sprint):
    """One row per space member: computed capacity vs allocated points.

    capacity = day rate (base_points / working days)
               × effective days (working − public holidays − leave)
               × role factor (team lead 0.8, tech lead 0.7)
    """
    space = sprint.space
    members = list(space.members.filter(is_active=True))
    saved = {c.user_id: c for c in sprint.capacities.all()}
    if sprint.start_date and sprint.end_date:
        days = working_days(sprint.start_date, sprint.end_date)
    else:
        days = 10  # default two-week sprint until dates are set

    allocated = {
        row['assignee']: row['p'] or 0
        for row in sprint_issue_qs(sprint).filter(assignee__isnull=False)
        .values('assignee').annotate(p=Sum('story_points'))
    }

    rows, total_capacity, total_allocated = [], 0.0, 0
    for member in members:
        cap = saved.get(member.pk) or SprintCapacity(sprint=sprint, user=member)
        day_rate = cap.base_points / days
        effective = max(days - sprint.public_holidays - cap.leave_days, 0)
        capacity = round(day_rate * effective * SprintCapacity.ROLE_FACTOR[cap.role], 1)
        points = allocated.get(member.pk, 0)
        rows.append({
            'user': member,
            'cap': cap,
            'effective_days': effective,
            'capacity': capacity,
            'allocated': points,
            'delta': round(capacity - points, 1),
            'over': points > capacity,
        })
        total_capacity += capacity
        total_allocated += points

    unassigned = (
        sprint_issue_qs(sprint).filter(assignee__isnull=True)
        .aggregate(p=Sum('story_points'))['p'] or 0
    )
    return {
        'rows': rows,
        'working_days': days,
        'total_capacity': round(total_capacity, 1),
        'total_allocated': total_allocated,
        'unassigned': unassigned,
        'fits': total_allocated + unassigned <= total_capacity,
    }


# ── Burndown ─────────────────────────────────────────────────────────────────

def _done_dates(sprint):
    """Best-effort completion date per done issue, from the activity log
    (status changes whose new value is a done-category status today)."""
    done_names = set(
        sprint.space.statuses.filter(category='done').values_list('name', flat=True)
    )
    issues = list(sprint_issue_qs(sprint).select_related('status'))
    done_at = {}
    activities = (
        Activity.objects
        .filter(issue__in=issues, field='status', new_value__in=done_names)
        .order_by('created_at')
    )
    for activity in activities:
        done_at[activity.issue_id] = activity.created_at.date()  # latest wins

    fallback = sprint.completed_at.date() if sprint.completed_at else sprint.end_date
    return issues, {
        issue.pk: done_at.get(issue.pk, fallback)
        for issue in issues if issue.is_done
    }


def burndown(sprint):
    """Daily remaining-points series + SVG polylines, or None without data."""
    if not (sprint.start_date and sprint.end_date):
        return None
    issues, done_dates = _done_dates(sprint)
    total = sum(issue.story_points or 0 for issue in issues)
    if total <= 0:
        return None

    days = []
    day = sprint.start_date
    while day <= sprint.end_date:
        days.append(day)
        day += datetime.timedelta(days=1)

    today = timezone.localdate()
    actual = []
    for day in days:
        if sprint.state != Sprint.STATE_COMPLETED and day > today:
            break
        burned = sum(
            (issue.story_points or 0) for issue in issues
            if done_dates.get(issue.pk) and done_dates[issue.pk] <= day
        )
        actual.append(total - burned)
    if not actual:
        actual = [total]

    n = len(days)

    def x(i):
        return PAD + i * (CHART_W - 2 * PAD) / max(n - 1, 1)

    def y(value):
        return PAD + (1 - value / total) * (CHART_H - 2 * PAD)

    return {
        'width': CHART_W,
        'height': CHART_H,
        'pad': PAD,
        'total': total,
        'remaining': actual[-1],
        'start': sprint.start_date,
        'end': sprint.end_date,
        'actual_points': ' '.join(f'{x(i):.1f},{y(v):.1f}' for i, v in enumerate(actual)),
        'ideal_points': f'{x(0):.1f},{y(total):.1f} {x(n - 1):.1f},{y(0):.1f}',
        'baseline_y': y(0),
        'top_y': y(total),
    }


# ── Velocity ─────────────────────────────────────────────────────────────────

def velocity(space, limit=8):
    """Completed points per completed sprint (oldest→newest), as SVG bars."""
    sprints = list(
        space.sprints.filter(state=Sprint.STATE_COMPLETED).order_by('completed_at')
    )[-limit:]
    if not sprints:
        return None

    bars = []
    for sprint in sprints:
        points = sum(
            (issue.story_points or 0)
            for issue in sprint_issue_qs(sprint).select_related('status')
            if issue.is_done
        )
        bars.append({'sprint': sprint, 'points': points})

    top = max((bar['points'] for bar in bars), default=0) or 1
    slot = (CHART_W - 2 * PAD) / len(bars)
    usable_h = CHART_H - 2 * PAD - 14
    for i, bar in enumerate(bars):
        width = min(slot * 0.6, 64)
        bar['x'] = PAD + i * slot + (slot - width) / 2
        bar['w'] = width
        bar['h'] = max(bar['points'] / top * usable_h, 2)
        bar['y'] = CHART_H - PAD - bar['h']
        bar['cx'] = PAD + i * slot + slot / 2

    average = round(sum(bar['points'] for bar in bars) / len(bars), 1)
    return {
        'bars': bars,
        'avg': average,
        'avg_y': CHART_H - PAD - (average / top * usable_h),
        'width': CHART_W,
        'height': CHART_H,
        'pad': PAD,
        'baseline_y': CHART_H - PAD,
    }
