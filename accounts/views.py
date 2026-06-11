from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .forms import (
    LoginForm, NotificationPreferenceForm, PasswordResetRequestForm,
    ProfileForm, SignupForm, StyledPasswordChangeForm, StyledSetPasswordForm,
)
from .models import NotificationPreference


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome to AtlasHub!')
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'accounts/signup.html', {'form': form})


class SignInView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class SignOutView(LogoutView):
    pass


class ChangePasswordView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, 'Your password has been changed.')
        return super().form_valid(form)


# ── Password reset ───────────────────────────────────────────────────────────
# Delivered over WhatsApp when the user has a linked phone AND the worker is
# connected; otherwise the standard email channel. Same response either way —
# never reveal whether an account exists.

def password_reset_request(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            User = get_user_model()
            email = form.cleaned_data['email'].lower()
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
            except User.DoesNotExist:
                user = None
            if user:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = settings.SITE_URL + reverse(
                    'accounts:password_reset_confirm',
                    kwargs={'uidb64': uid, 'token': token},
                )
                context = {'user': user, 'reset_url': reset_url}

                from whatsapp.client import service
                from whatsapp.models import WhatsAppMessage
                phone = (user.phone or '').strip()
                if phone and service.is_connected:
                    service.enqueue(
                        phone,
                        render_to_string('accounts/password_reset_whatsapp.txt', context),
                        user=user,
                        msg_type=WhatsAppMessage.PASSWORD_RESET,
                    )
                else:
                    send_mail(
                        'Reset your AtlasHub password',
                        render_to_string('accounts/password_reset_email.txt', context),
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=True,
                    )
            return redirect('accounts:password_reset_done')
    else:
        form = PasswordResetRequestForm()
    return render(request, 'accounts/password_reset_form.html', {'form': form})


def password_reset_done(request):
    return render(request, 'accounts/password_reset_done.html')


def password_reset_confirm(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    valid = user is not None and default_token_generator.check_token(user, token)

    form = None
    if valid:
        if request.method == 'POST':
            form = StyledSetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Password reset — you can now log in.')
                return redirect('accounts:password_reset_complete')
        else:
            form = StyledSetPasswordForm(user)
    return render(request, 'accounts/password_reset_confirm.html', {'form': form, 'valid': valid})


def password_reset_complete(request):
    return render(request, 'accounts/password_reset_complete.html')


@login_required
def profile(request):
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
    profile_form = ProfileForm(instance=request.user)
    prefs_form = NotificationPreferenceForm(instance=prefs)

    if request.method == 'POST':
        if 'save_profile' in request.POST:
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated.')
                return redirect('accounts:profile')
        elif 'save_prefs' in request.POST:
            prefs_form = NotificationPreferenceForm(request.POST, instance=prefs)
            if prefs_form.is_valid():
                prefs_form.save()
                messages.success(request, 'Notification preferences saved.')
                return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'prefs_form': prefs_form,
    })
