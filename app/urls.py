from django.contrib import admin
from django.urls import include, path

from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', core_views.dashboard, name='dashboard'),
    path('', include('core.urls')),
    path('', include('projects.urls')),
    path('', include('wiki.urls')),
    path('', include('whatsapp.urls')),
]
