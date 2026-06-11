from django.urls import path

from . import views

app_name = 'whatsapp'

urlpatterns = [
    path('whatsapp/', views.dashboard, name='dashboard'),
    path('whatsapp/link/', views.link_device, name='link_device'),
    path('whatsapp/link/status/', views.link_status, name='link_status'),
    path('whatsapp/status/', views.status_panel, name='status_panel'),
    path('whatsapp/queue/', views.message_queue_partial, name='message_queue_partial'),
    path('whatsapp/restart/', views.restart_service, name='restart_service'),
    path('whatsapp/disconnect/', views.disconnect_service, name='disconnect_service'),
    path('whatsapp/send/', views.send_message, name='send_message'),
]
