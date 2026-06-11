from django.urls import path

from . import views

app_name = 'wiki'

urlpatterns = [
    path('wiki/', views.home, name='home'),
    path('wiki/<str:key>/', views.space_home, name='space_home'),
    path('wiki/<str:key>/create/', views.page_create, name='page_create'),
    path('wiki/<str:key>/reorder/', views.tree_reorder, name='tree_reorder'),
    path('wiki/<str:key>/preview/', views.preview, name='preview'),
    path('wiki/<str:key>/diagrams/create/', views.diagram_create, name='diagram_create'),
    path('wiki/<str:key>/diagrams/<int:diagram_id>/edit/', views.diagram_edit, name='diagram_edit'),
    path('wiki/<str:key>/diagrams/<int:diagram_id>/save/', views.diagram_save, name='diagram_save'),
    path('wiki/<str:key>/<slug:slug>/', views.page_view, name='page'),
    path('wiki/<str:key>/<slug:slug>/edit/', views.page_edit, name='page_edit'),
    path('wiki/<str:key>/<slug:slug>/move/', views.page_move, name='page_move'),
    path('wiki/<str:key>/<slug:slug>/publish/', views.page_publish, name='page_publish'),
    path('wiki/<str:key>/<slug:slug>/restrict/', views.page_restrict, name='page_restrict'),
    path('wiki/<str:key>/<slug:slug>/history/', views.page_history, name='page_history'),
    path('wiki/<str:key>/<slug:slug>/restore/<int:version_id>/', views.page_restore, name='page_restore'),
    path('wiki/<str:key>/<slug:slug>/delete/', views.page_delete, name='page_delete'),
    path('wiki/<str:key>/<slug:slug>/comments/', views.comment_add, name='comment_add'),
    path('wiki/<str:key>/<slug:slug>/comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
]
