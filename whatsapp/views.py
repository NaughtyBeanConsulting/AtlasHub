from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .client import service
from .models import WhatsAppMessage


def _manages_session():
    """This app only manages the WhatsApp session (pair/restart/disconnect) when
    it owns the worker. When it shares another app's worker this is False, making
    the UI status-only."""
    return getattr(settings, 'WHATSAPP_MANAGES_SESSION', True)


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden('Staff access required.')
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_required
def dashboard(request):
    return render(request, 'whatsapp/dashboard.html', {
        'info': service.info,
        'recent_messages': WhatsAppMessage.objects.select_related('user')[:20],
        'manages_session': _manages_session(),
    })


@staff_required
def status_panel(request):
    """HTMX polling partial — connection status + QR code."""
    return render(request, 'whatsapp/partials/status_panel.html', {
        'info': service.info,
        'manages_session': _manages_session(),
    })


@staff_required
def message_queue_partial(request):
    """HTMX polling partial — message queue table."""
    return render(request, 'whatsapp/partials/message_queue.html', {
        'recent_messages': WhatsAppMessage.objects.select_related('user')[:20],
    })


@staff_required
def link_device(request):
    """Dedicated full-screen page for QR code scanning and device linking."""
    if not _manages_session():
        messages.info(request, 'WhatsApp pairing is managed centrally (ClockInSop).')
        return redirect('whatsapp:dashboard')
    return render(request, 'whatsapp/link_device.html', {'info': service.info})


@staff_required
def link_status(request):
    """HTMX partial used only on the link-device page."""
    return render(request, 'whatsapp/partials/link_status.html', {'info': service.info})


@staff_required
@require_POST
def restart_service(request):
    service.restart()
    messages.success(request, 'WhatsApp worker is restarting…')
    return redirect('whatsapp:dashboard')


@staff_required
@require_POST
def disconnect_service(request):
    service.disconnect()
    messages.success(request, 'Logged out — a fresh QR code will appear shortly.')
    return redirect('whatsapp:link_device')


@staff_required
@require_POST
def send_message(request):
    phone = request.POST.get('phone', '').strip()
    message = request.POST.get('message', '').strip()
    if not phone or not message:
        messages.error(request, 'Phone number and message are required.')
        return redirect('whatsapp:dashboard')
    service.enqueue(phone, message, msg_type=WhatsAppMessage.MANUAL)
    messages.success(request, f'Message queued for {phone}.')
    return redirect('whatsapp:dashboard')
