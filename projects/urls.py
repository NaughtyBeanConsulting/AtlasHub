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
    path('browse/<str:issue_key>/', views.issue_browse, name='browse'),
]
