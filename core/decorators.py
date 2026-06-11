from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from .models import Space, SpaceMembership


def space_required(role=SpaceMembership.ROLE_VIEWER, space_type=None):
    """Resolve the <key> URL kwarg to a Space and enforce a minimum role.

    The wrapped view receives the space as its second argument:
        @space_required(role='member', space_type='software')
        def backlog(request, space): ...

    Non-members get a 404 (membership is private), members below the
    required role get a 403. The resolved role is stashed on the request
    for templates (request.space_role).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, key, *args, **kwargs):
            lookup = {'key': key.upper()}
            if space_type:
                lookup['space_type'] = space_type
            space = get_object_or_404(Space, **lookup)
            user_role = space.role_for(request.user)
            if user_role is None:
                raise Http404
            if SpaceMembership.ROLE_RANK[user_role] < SpaceMembership.ROLE_RANK[role]:
                return HttpResponseForbidden('You need a higher role in this space to do that.')
            request.space = space
            request.space_role = user_role
            return view_func(request, space, *args, **kwargs)
        return wrapper
    return decorator
