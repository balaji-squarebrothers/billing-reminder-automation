from collections import defaultdict
from datetime import timedelta
import json

from django.contrib import messages

from django.shortcuts import get_object_or_404, redirect, render

from django.utils import timezone
from billing.utils import user_can, get_user_permissions

from django.core.paginator import Paginator

from billing.services.email_service import send_otp_email, send_reminder_email

from billing.models import ActionTracker, EmailLog, Invoice, EmailTemplate, Notification, NotificationRead

from django.contrib.auth.decorators import login_required

from billing.tasks import send_email_task

from django.http import JsonResponse
from django.views.decorators.http import require_POST

@login_required
def invoice_list(request):
    payment_filter = request.GET.get('payment_status')
    workflow_filter = request.GET.get('workflow_status')
    due_filter = request.GET.get("due_filter")
    search_query = request.GET.get('search')

    Invoice.objects.select_related('client').only(
        "id", "status", "duedate", "total", "client__email", "client__firstname", "client__lastname"
    ).prefetch_related("items")

    if payment_filter == "paid":
        invoices = invoices.filter(status="Paid")

    elif payment_filter == "unpaid":
        invoices = invoices.exclude(status="Paid")

    if workflow_filter == "suspended":
        invoices = invoices.filter(tracker__suspension_sent=True)

    elif workflow_filter == "confirmation":
        invoices = invoices.filter(tracker__confirmation_sent=True)

    elif workflow_filter == "queue":
        invoices = invoices.filter(tracker__queue_sent=True)

    elif workflow_filter == "terminated":
        invoices = invoices.filter(tracker__termination_sent=True)

    if due_filter == "today":
        invoices = invoices.filter(duedate=timezone.now().date())

    elif due_filter == "tomorrow":
        invoices = invoices.filter(
            duedate=timezone.now().date() + timedelta(days=1)
        )

    trackers = { t.invoice.id: t for t in ActionTracker.objects.select_related('invoice')}

    grouped_templates = defaultdict(list)

    for t in EmailTemplate.objects.all():
        grouped_templates[t.template_type].append({
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "body": t.body
        })

    failed_logs = {
        (log.invoice_id, log.email_type): log
        for log in EmailLog.objects.filter(status="failed")
    }

    for invoice in invoices:
        tracker = trackers.get(invoice.id)

        if not tracker:
            continue

        invoice.suspension_sent = tracker.suspension_sent
        invoice.termination_sent = tracker.termination_sent
        invoice.confirmation_sent = tracker.confirmation_sent
        invoice.queue_sent = tracker.queue_sent
        invoice.confirmation_token = tracker.confirmation_token or ""
        invoice.failed_due_today = failed_logs.get((invoice.id, "due_today"))
        invoice.failed_due_tomorrow = failed_logs.get((invoice.id, "due_tomorrow"))

        client = invoice.client if invoice.client else None

        invoice.name = str(client) if client else "Unknown"
        invoice.email = client.email if client and client.email else ""
        invoice.amount = invoice.total

        if invoice.status == "Paid":
            invoice.display_status = "paid"
        elif tracker.termination_sent:
            invoice.display_status = "terminated"
        elif tracker.suspension_sent:
            invoice.display_status = "suspended"
        else:
            invoice.display_status = "unpaid"

        if search_query and search_query.lower() not in (str(invoice.id).lower() + (invoice.name or "").lower()):
            continue

        item = invoice.items.first() if hasattr(invoice, 'items') else None

        invoice.domain = item.domain_name if item else ""
        invoice.plan = item.plan_name if item else ""
        invoice.service = item.item_type if item else ""

    paginator = Paginator(invoices, 10)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "invoice_list.html", {
        "page_obj": page_obj,
        "templates_json": json.dumps(grouped_templates, ensure_ascii=False),
        "user_permissions": get_user_permissions(request.user),
        "today": timezone.now().date(),
        "tomorrow": timezone.now().date() + timedelta(days=1),
    })

@login_required
def send_email(request, email_type, invoice_id):
    if not can_send_action(request.user, email_type):
        messages.error(request, "You are not allowed to perform this action")
        return redirect('invoice_list')
    
    if request.method != "POST":
        return redirect('invoice_list')
    
    invoice = get_object_or_404(Invoice.objects.select_related('client'), id=invoice_id)

    if invoice.status == "Paid":
        messages.warning(request, "Already paid")
        return redirect('invoice_list')
    
    client = invoice.client

    item = invoice.items.first()

    subject = request.POST.get("subject", "")
    body = request.POST.get("body", "")
    include_confirm_link = request.POST.get("include_confirm_link") == "on"

    task = send_email_task.delay(
        invoice_id=invoice.id,
        email_type=email_type,
        recipient_email=client.email,
        subject=subject,
        body=body,
        include_confirm_link=include_confirm_link,
        sent_by_id=request.user.id
    )

    request.session['last_task_id'] = task.id

    messages.success(request, "Email is being sent...")

    return redirect('invoice_list')

@login_required
@require_POST
def retry_email(request):
    invoice_id = request.POST.get("invoice_id")
    email_type = request.POST.get("email_type")

    log = EmailLog.objects.filter(
        invoice_id=invoice_id,
        email_type=email_type,
        status="failed"
    ).last()

    if not log:
        return JsonResponse({"error": "No failed email found"}, status=400)

    template = EmailTemplate.objects.filter(
        template_type=email_type,
        is_active=True
    ).first()

    if not template:
        return JsonResponse({"error": "Template not found"}, status=400)

    send_email_task.delay(
        invoice_id=invoice_id,
        email_type=email_type,
        recipient_email=log.invoice.client.email,
        subject=template.subject,
        body=template.body
    )

    return JsonResponse({"success": True})

def confirm_termination(request, token):
    tracker = get_object_or_404(
        ActionTracker,
        confirmation_token=token,
        confirmation_token__isnull=False
    )

    if not tracker:
        return render(request, "confirmation_response.html", {
            "accepted": True,
            "tracker": None
        })
    
    if tracker.confirmation_expires_at and tracker.confirmation_expires_at < timezone.now():
        return render(request, "confirmation_response.html", {
            "tracker": tracker,
            "expired": True
        })

    if tracker.confirmation_response == "yes":
        return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": True, "accepted": False})

    otp_still_valid = (
        tracker.otp_expires_at and
        tracker.otp_expires_at > timezone.now() and
        tracker.otp_code
    )

    if not otp_still_valid:
        send_otp_email(tracker)

    return render(request, "otp_verify.html", {"token": token})

def verify_otp(request, token):
    if request.method != "POST":
        return redirect('confirm_termination', token=token)
    
    
    tracker = get_object_or_404(ActionTracker, confirmation_token=token, confirmation_token__isnull=False)

    if not tracker:
        return render(request, "confirmation_response.html", {
            "accepted": True,
            "tracker": None
        })
    
    if tracker.confirmation_expires_at and tracker.confirmation_expires_at < timezone.now():
        return render(request, "confirmation_response.html", {
            "tracker": tracker,
            "expired": True
        })

    if tracker.confirmation_response == "yes":
        return render(request, "confirmation_response.html", {
            "tracker": tracker,
            "already": True
        })
    

    entered_otp = request.POST.get("otp", "").strip()

    if not tracker.otp_expires_at or tracker.otp_expires_at < timezone.now():
        return render(request, "otp_verify.html", {
            "token": token,
            "error": "OTP has expired. Please go back and request a new one."
        })
    
    if entered_otp != tracker.otp_code:
        print(entered_otp)
        return render(request, "otp_verify.html", {
            "token": token,
            "error": "Invalid OTP. Please try again."
        })
    
    tracker.otp_verified = True
    tracker.otp_code = None
    tracker.confirmation_response = "yes"
    tracker.responded_at = timezone.now()
    tracker.confirmation_token = None
    tracker.save()

    Notification.objects.create(
        invoice=tracker.invoice,
        message=f"Client verified OTP and confirmed termination for invoice {tracker.invoice.id}.",
        type="action"
    )

    return render(request, "confirmation_response.html", {
        "tracker": tracker,
        "accepted": True
    })

def resend_otp(request, token):
    if request.method != "POST":
        return redirect('confirm_termination', token=token)

    tracker = get_object_or_404(
        ActionTracker,
        confirmation_token=token,
        confirmation_token__isnull=False
    )

    if tracker.confirmation_expires_at and tracker.confirmation_expires_at < timezone.now():
        return render(request, "confirmation_response.html", {
            "tracker": tracker,
            "expired": True
        })

    if tracker.confirmation_response == "yes":
        return render(request, "confirmation_response.html", {
            "tracker": tracker,
            "already": True
        })

    send_otp_email(tracker)

    return render(request, "otp_verify.html", {
        "token": token,
        "resent": True
    })

@login_required
def notification_list(request):
    notifications = Notification.objects.order_by('-created_at')
    for notification in notifications:
        NotificationRead.objects.get_or_create(
            notification=notification,
            user=request.user
        )

    return render(request, 'notification_list.html', {
        'notifications': notifications
    })

def template_list(request):
    templates = EmailTemplate.objects.all()
    return render(request, "template_list.html", {"templates": templates})

def custom_404(request, exception):
    if request.path.startswith('/confirm/'):
        return render(request, "confirmation_response.html", {
            "accepted": True, "tracker": None
        }, status=404)
    
    if not request.user.is_authenticated:
        return redirect('login')
    
    return redirect('invoice_list')

def can_send_action(user, action):
    return user_can(user, f"send_{action}")