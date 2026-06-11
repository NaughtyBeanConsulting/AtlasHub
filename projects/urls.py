from django.urls import path

from . import views

app_name = 'projects'

urlpatterns = [
    path('projects/', views.home, name='home'),
    path('projects/<str:key>/', views.project_home, name='project_home'),
    path('projects/<str:key>/backlog/', views.backlog, name='backlog'),
    path('projects/<str:key>/backlog/reorder/', views.backlog_reorder, name='backlog_reorder'),
    path('projects/<str:key>/issues/create-inline/', views.issue_create_inline, name='issue_create_inline'),
    path('projects/<str:key>/epics/create/', views.epic_create, name='epic_create'),
    path('projects/<str:key>/board/', views.board, name='board'),
    path('projects/<str:key>/board/move/', views.board_move, name='board_move'),
    path('projects/<str:key>/sprints/create/', views.sprint_create, name='sprint_create'),
    path('projects/<str:key>/sprints/move/', views.sprint_move, name='sprint_move'),
    path('projects/<str:key>/sprints/<int:sprint_id>/start/', views.sprint_start, name='sprint_start'),
    path('projects/<str:key>/sprints/<int:sprint_id>/complete/', views.sprint_complete, name='sprint_complete'),
    path('browse/<str:issue_key>/', views.issue_browse, name='browse'),
]
