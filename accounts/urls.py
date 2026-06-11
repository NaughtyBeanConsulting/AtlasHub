from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.SignInView.as_view(), name='login'),
    path('logout/', views.SignOutView.as_view(), name='logout'),
    path('password-change/', views.ChangePasswordView.as_view(), name='password_change'),
    path('profile/', views.profile, name='profile'),
    # Password reset (WhatsApp first, email fallback)
    path('forgot-password/', views.password_reset_request, name='password_reset'),
    path('forgot-password/sent/', views.password_reset_done, name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.password_reset_confirm, name='password_reset_confirm'),
    path('reset/done/', views.password_reset_complete, name='password_reset_complete'),
]
