from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('spaces/create/', views.space_create, name='space_create'),
    path('spaces/<str:key>/settings/', views.space_settings, name='space_settings'),
]
