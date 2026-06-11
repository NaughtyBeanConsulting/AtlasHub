def nav_spaces(request):
    """Spaces for the topnav product menus (Jira / Confluence)."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    spaces = list(request.user.spaces.all()[:30])
    return {
        'nav_software_spaces': [s for s in spaces if s.space_type == 'software'][:8],
        'nav_wiki_spaces': [s for s in spaces if s.space_type == 'wiki'][:8],
    }
