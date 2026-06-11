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
    path('projects/<str:key>/timeline/', views.timeline, name='timeline'),
    path('projects/<str:key>/mentions/', views.mentions, name='mentions'),
    path('browse/<str:issue_key>/', views.issue_browse, name='browse'),
    path('browse/<str:issue_key>/panel/', views.issue_panel, name='issue_panel'),
    path('browse/<str:issue_key>/field/<str:field>/', views.issue_field, name='issue_field'),
    path('browse/<str:issue_key>/comments/', views.comment_add, name='comment_add'),
    path('browse/<str:issue_key>/comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    path('browse/<str:issue_key>/ac/', views.ac_add, name='ac_add'),
    path('browse/<str:issue_key>/ac/<int:ac_id>/toggle/', views.ac_toggle, name='ac_toggle'),
    path('browse/<str:issue_key>/ac/<int:ac_id>/delete/', views.ac_delete, name='ac_delete'),
    path('browse/<str:issue_key>/subtasks/', views.subtask_add, name='subtask_add'),
    path('browse/<str:issue_key>/activity/', views.issue_activity, name='issue_activity'),
]
