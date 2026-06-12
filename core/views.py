from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .decorators import space_required
from .forms import AddMemberForm, SpaceForm
from .models import Space, SpaceMembership


@space_required()
def mentions(request, space):
    """JSON autocomplete source for @mentions (space members) — shared by the
    issue and wiki editors."""
    q = request.GET.get('q', '').strip()
    members = space.members.filter(is_active=True)
    if q:
        members = (
            members.filter(first_name__icontains=q)
            | members.filter(last_name__icontains=q)
            | members.filter(email__icontains=q)
        )
    return JsonResponse({'results': [
        {'id': m.pk, 'name': m.display_name} for m in members.distinct()[:8]
    ]})


def _filter_visible_pages(user, pages, limit):
    from wiki.services import filter_pages_for_user
    return filter_pages_for_user(user, pages, limit=limit)


@login_required
def dashboard(request):
    from projects.models import Issue
    from wiki.models import Page

    spaces = list(request.user.spaces.all())
    assigned = (
        Issue.objects
        .filter(assignee=request.user, space__in=spaces, archived=False)
        .exclude(status__category='done')
        .select_related('status', 'space', 'epic')
        .order_by('-updated_at')[:10]
    )
    recent_pages = _filter_visible_pages(
        request.user,
        Page.objects.filter(space__in=spaces)
        .select_related('space', 'updated_by')
        .order_by('-updated_at')[:30],
        limit=6,
    )
    return render(request, 'core/dashboard.html', {
        'software_spaces': [s for s in spaces if s.space_type == Space.TYPE_SOFTWARE],
        'wiki_spaces': [s for s in spaces if s.space_type == Space.TYPE_WIKI],
        'assigned_issues': assigned,
        'recent_pages': recent_pages,
    })


def _search_results(request, limit):
    from django.db.models import Q

    from projects.models import Issue
    from wiki.models import Page

    q = request.GET.get('q', '').strip()
    if not q:
        return q, [], []
    spaces = request.user.spaces.all()
    issues = (
        Issue.objects.filter(space__in=spaces, archived=False)
        .filter(Q(key__icontains=q) | Q(summary__icontains=q))
        .select_related('status', 'space', 'assignee')
        .order_by('-updated_at')[:limit]
    )
    pages = _filter_visible_pages(
        request.user,
        Page.objects.filter(space__in=spaces, title__icontains=q)
        .select_related('space')
        .order_by('-updated_at')[:limit * 4],
        limit=limit,
    )
    return q, list(issues), pages


@login_required
def search(request):
    q, issues, pages = _search_results(request, limit=25)
    return render(request, 'core/search.html', {'q': q, 'issues': issues, 'pages': pages})


@login_required
def quick_search(request):
    """Topnav dropdown partial."""
    q, issues, pages = _search_results(request, limit=5)
    return render(request, 'core/partials/quick_search.html',
                  {'q': q, 'issues': issues, 'pages': pages})


@login_required
def space_create(request):
    initial = {}
    if request.GET.get('type') in (Space.TYPE_SOFTWARE, Space.TYPE_WIKI):
        initial['space_type'] = request.GET['type']
    if request.method == 'POST':
        form = SpaceForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                space = form.save(commit=False)
                space.created_by = request.user
                space.save()
                SpaceMembership.objects.create(
                    space=space, user=request.user, role=SpaceMembership.ROLE_ADMIN,
                )
            messages.success(request, f'{space.get_space_type_display()} “{space.name}” created.')
            if space.space_type == Space.TYPE_SOFTWARE:
                return redirect('projects:backlog', key=space.key)
            return redirect('wiki:space_home', key=space.key)
    else:
        form = SpaceForm(initial=initial)
    return render(request, 'core/space_form.html', {'form': form})


@space_required(role=SpaceMembership.ROLE_ADMIN)
def space_settings(request, space):
    add_form = AddMemberForm(space=space)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_member':
            add_form = AddMemberForm(request.POST, space=space)
            if add_form.is_valid():
                SpaceMembership.objects.create(
                    space=space,
                    user=add_form.cleaned_data['user'],
                    role=add_form.cleaned_data['role'],
                )
                messages.success(request, f"{add_form.cleaned_data['user'].display_name} added.")
                return redirect('core:space_settings', key=space.key)
        elif action == 'change_role':
            membership = space.memberships.filter(pk=request.POST.get('membership')).first()
            role = request.POST.get('role')
            if membership and role in SpaceMembership.ROLE_RANK:
                membership.role = role
                membership.save(update_fields=['role'])
                messages.success(request, f'{membership.user.display_name} is now a {role}.')
            return redirect('core:space_settings', key=space.key)
        elif action == 'remove_member':
            membership = space.memberships.filter(pk=request.POST.get('membership')).first()
            if membership:
                if membership.user_id == request.user.id:
                    messages.error(request, "You can't remove yourself.")
                else:
                    membership.delete()
                    messages.success(request, f'{membership.user.display_name} removed.')
            return redirect('core:space_settings', key=space.key)
        elif action == 'delete_space':
            if request.POST.get('confirm_key') == space.key:
                name = space.name
                space.delete()
                messages.success(request, f'“{name}” was deleted.')
                return redirect('dashboard')
            messages.error(request, 'Type the space key to confirm deletion.')
            return redirect('core:space_settings', key=space.key)

    return render(request, 'core/space_settings.html', {
        'space': space,
        'memberships': space.memberships.select_related('user'),
        'add_form': add_form,
        'roles': SpaceMembership.ROLE_CHOICES,
    })
