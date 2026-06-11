from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.SignInView.as_view(), name='login'),
    path('logout/', views.SignOutView.as_view(), name='logout'),
    path('password-change/', views.ChangePasswordView.as_view(), name='password_change'),
    path('profile/', views.profile, name='profile'),
]
