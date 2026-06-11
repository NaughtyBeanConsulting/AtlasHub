from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from core.decorators import space_required
from core.markdown import render_markdown
from core.models import Space, SpaceMembership

from .models import Diagram, Page, PageComment, PageVersion, unique_slug
from .notifications import notify_page_mentions
from .services import render_page_html


@login_required
def home(request):
    spaces = (
        request.user.spaces
        .filter(space_type=Space.TYPE_WIKI)
        .annotate(page_count=Count('pages'))
    )
    return render(request, 'wiki/home.html', {'spaces': spaces})


def _tree(space, current_page=None):
    """All pages as a nested structure: roots with .child_nodes attached."""
    pages = list(space.pages.all())
    by_parent = {}
    for page in pages:
        by_parent.setdefault(page.parent_id, []).append(page)
    for page in pages:
        page.child_nodes = by_parent.get(page.id, [])
    return by_parent.get(None, [])


def _wiki_context(request, space, page=None, **extra):
    context = {
        'space': space,
        'tree': _tree(space),
        'current_page_id': page.pk if page else None,
        'page': page,
        'can_edit': SpaceMembership.ROLE_RANK[request.space_role]
        >= SpaceMembership.ROLE_RANK[SpaceMembership.ROLE_MEMBER],
    }
    context.update(extra)
    return context


@space_required(space_type=Space.TYPE_WIKI)
def space_home(request, space):
    first = space.pages.filter(parent__isnull=True).first()
    if first:
        return redirect('wiki:page', key=space.key, slug=first.slug)
    return render(request, 'wiki/space_home.html', _wiki_context(request, space))


@space_required(space_type=Space.TYPE_WIKI)
def page_view(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    context = _wiki_context(request, space, page)
    return render(request, 'wiki/page_view.html', {
        **context,
        'breadcrumbs': page.ancestors(),
        'html': render_page_html(page, can_edit=context['can_edit']),
        'comments': page.comments.select_related('author'),
    })


def _snapshot(page, user):
    number = (page.versions.aggregate(m=Max('number'))['m'] or 0) + 1
    PageVersion.objects.create(
        page=page, number=number, title=page.title, body_md=page.body_md, edited_by=user,
    )


@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_create(request, space):
    parent = None
    parent_id = request.GET.get('parent') or request.POST.get('parent')
    if parent_id:
        parent = get_object_or_404(Page, pk=parent_id, space=space)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Pages need a title.')
        else:
            position = (
                space.pages.filter(parent=parent).aggregate(m=Max('position'))['m'] or 0
            ) + 1
            page = Page.objects.create(
                space=space, parent=parent, title=title,
                slug=unique_slug(space, title),
                body_md=request.POST.get('body_md', ''),
                position=position,
                created_by=request.user, updated_by=request.user,
            )
            _snapshot(page, request.user)
            notify_page_mentions(page, request.user, page.body_md)
            messages.success(request, f'“{page.title}” created.')
            return redirect('wiki:page', key=space.key, slug=page.slug)

    return render(request, 'wiki/page_form.html',
                  _wiki_context(request, space, None, parent=parent, mode='create'))


@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_edit(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, 'Pages need a title.')
        else:
            if title != page.title:
                page.slug = unique_slug(space, title, exclude_pk=page.pk)
            page.title = title
            page.body_md = request.POST.get('body_md', '')
            page.updated_by = request.user
            page.save()
            _snapshot(page, request.user)
            notify_page_mentions(page, request.user, page.body_md)
            messages.success(request, 'Page saved.')
            return redirect('wiki:page', key=space.key, slug=page.slug)
    return render(request, 'wiki/page_form.html',
                  _wiki_context(request, space, page, mode='edit',
                                diagrams=page.diagrams.all()))


@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_move(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    blocked = page.descendant_pks() | {page.pk}
    candidates = space.pages.exclude(pk__in=blocked)
    if request.method == 'POST':
        target_id = request.POST.get('parent') or None
        target = None
        if target_id:
            target = get_object_or_404(Page, pk=target_id, space=space)
            if target.pk in blocked:
                return HttpResponseBadRequest("You can't move a page under itself.")
        page.parent = target
        page.position = (
            space.pages.filter(parent=target).aggregate(m=Max('position'))['m'] or 0
        ) + 1
        page.save(update_fields=['parent', 'position', 'updated_at'])
        messages.success(
            request,
            f'Moved “{page.title}” under “{target.title}”.' if target
            else f'Moved “{page.title}” to the top level.',
        )
        return redirect('wiki:page', key=space.key, slug=page.slug)
    return render(request, 'wiki/page_move.html',
                  _wiki_context(request, space, page, candidates=candidates,
                                breadcrumbs=page.ancestors()))


@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_history(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    return render(request, 'wiki/page_history.html',
                  _wiki_context(request, space, page,
                                versions=page.versions.select_related('edited_by'),
                                breadcrumbs=page.ancestors()))


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_restore(request, space, slug, version_id):
    page = get_object_or_404(Page, space=space, slug=slug)
    version = get_object_or_404(PageVersion, pk=version_id, page=page)
    page.title = version.title
    page.body_md = version.body_md
    page.updated_by = request.user
    page.save()
    _snapshot(page, request.user)
    messages.success(request, f'Restored “{page.title}” to version {version.number}.')
    return redirect('wiki:page', key=space.key, slug=page.slug)


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def page_delete(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    # Children move up a level rather than being deleted.
    page.children.update(parent=page.parent)
    parent = page.parent
    title = page.title
    page.delete()
    messages.success(request, f'“{title}” deleted. Its sub-pages moved up a level.')
    if parent:
        return redirect('wiki:page', key=space.key, slug=parent.slug)
    return redirect('wiki:space_home', key=space.key)


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def tree_reorder(request, space):
    """Sibling reorder from the sidebar tree (same-parent lists only)."""
    parent_id = request.POST.get('parent') or None
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    pages = {p.pk: p for p in space.pages.filter(pk__in=ids)}
    if len(pages) != len(ids):
        return HttpResponseBadRequest('Stale tree — reload the page.')
    to_update = []
    for index, pk in enumerate(int(i) for i in ids):
        target = pages[pk]
        if str(target.parent_id or '') != str(parent_id or ''):
            continue  # cross-parent moves use the Move action
        if target.position != index:
            target.position = index
            to_update.append(target)
    Page.objects.bulk_update(to_update, ['position'])
    return HttpResponse(status=204)


@require_POST
@space_required(space_type=Space.TYPE_WIKI)
def preview(request, space):
    """Server-rendered markdown preview — identical pipeline to page view."""
    body = request.POST.get('body_md', '')
    page = None
    if request.POST.get('page'):
        page = space.pages.filter(pk=request.POST['page']).first()
    if page:
        original = page.body_md
        page.body_md = body
        html = render_page_html(page, can_edit=False)
        page.body_md = original
    else:
        html = render_markdown(body)
    return HttpResponse(f'<div class="prose-ah">{html}</div>')


# ── Diagrams (draw.io embed) ─────────────────────────────────────────────────

@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def diagram_create(request, space):
    page = get_object_or_404(Page, pk=request.POST.get('page'), space=space)
    diagram = Diagram.objects.create(
        page=page, title=request.POST.get('title', '').strip() or 'Untitled diagram',
    )
    return JsonResponse({'id': diagram.pk, 'fence': diagram.fence})


@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
@xframe_options_sameorigin
def diagram_edit(request, space, diagram_id):
    diagram = get_object_or_404(Diagram, pk=diagram_id, page__space=space)
    return render(request, 'wiki/diagram_edit.html', {
        'space': space,
        'diagram': diagram,
        'page': diagram.page,
    })


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def diagram_save(request, space, diagram_id):
    diagram = get_object_or_404(Diagram, pk=diagram_id, page__space=space)
    diagram.xml = request.POST.get('xml', '')
    diagram.svg = request.POST.get('svg', '')
    if request.POST.get('title', '').strip():
        diagram.title = request.POST['title'].strip()
    diagram.save()
    return JsonResponse({'ok': True})


# ── Comments ─────────────────────────────────────────────────────────────────

@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def comment_add(request, space, slug):
    page = get_object_or_404(Page, space=space, slug=slug)
    body = request.POST.get('body_md', '').strip()
    if body:
        PageComment.objects.create(page=page, author=request.user, body_md=body)
        notify_page_mentions(page, request.user, body)
    return render(request, 'wiki/partials/page_comments.html',
                  _wiki_context(request, space, page,
                                comments=page.comments.select_related('author')))


@require_POST
@space_required(role=SpaceMembership.ROLE_MEMBER, space_type=Space.TYPE_WIKI)
def comment_delete(request, space, slug, comment_id):
    page = get_object_or_404(Page, space=space, slug=slug)
    comment = get_object_or_404(PageComment, pk=comment_id, page=page)
    if comment.author_id == request.user.id or request.space_role == SpaceMembership.ROLE_ADMIN:
        comment.delete()
    return render(request, 'wiki/partials/page_comments.html',
                  _wiki_context(request, space, page,
                                comments=page.comments.select_related('author')))
