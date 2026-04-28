from collections import defaultdict
import json

import uuid

from django.contrib import messages

from django.shortcuts import get_object_or_404, redirect, render

from django.template import Context, Template

from django.utils import timezone

from django.core.paginator import Paginator

from billing.services.email_service import send_reminder_email

from billing.models import ActionTracker, Invoice, MessageTemplate, Notification

from django.contrib.auth.decorators import login_required

@login_required
def invoice_list(request):
    payment_filter = request.GET.get('payment_status')
    workflow_filter = request.GET.get('workflow_status')
    search_query = request.GET.get('search')

    invoices = Invoice.objects.select_related('client').prefetch_related('items')

    enriched = []

    trackers = { t.invoice.id: t for t in ActionTracker.objects.select_related('invoice')}

    grouped_templates = defaultdict(list)

    for t in MessageTemplate.objects.all():
        grouped_templates[t.template_type].append({
            "id": t.id,
            "name": t.name,
            "subject": t.subject,
            "body": t.body
        })

    for invoice in invoices:
        tracker = trackers.get(invoice.id)

        if not tracker:
            tracker = ActionTracker.objects.create(invoice=invoice)
            trackers[invoice.id] = tracker

        invoice.suspension_sent = tracker.suspension_sent
        invoice.termination_sent = tracker.termination_sent
        invoice.confirmation_sent = tracker.confirmation_sent
        invoice.queue_sent = tracker.queue_sent
        invoice.confirmation_token = tracker.confirmation_token or ""

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

        if payment_filter:
            if payment_filter == "paid" and invoice.status != "Paid":
                continue
            if payment_filter == "unpaid" and invoice.status == "Paid":
                continue

        if workflow_filter:
            if workflow_filter == "suspended" and not tracker.suspension_sent:
                continue
            if workflow_filter == "confirmation" and not tracker.confirmation_sent:
                continue
            if workflow_filter == "queue" and not tracker.queue_sent:
                continue
            if workflow_filter == "terminated" and not tracker.termination_sent:
                continue

        if search_query and search_query.lower() not in (str(invoice.id).lower() + (invoice.name or "").lower()):
            continue

        item = invoice.items.first() if hasattr(invoice, 'items') else None

        invoice.domain = item.domain_name if item else ""
        invoice.plan = item.plan_name if item else ""
        invoice.service = item.item_type if item else ""

        enriched.append(invoice)

    paginator = Paginator(enriched, 10)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "invoice_list.html", {
        "page_obj": page_obj,
        "templates_json": json.dumps(grouped_templates, ensure_ascii=False),

        "can_edit_email": can_edit_email(request.user),
        "is_trainee": is_trainee(request.user)
    })

@login_required
def notify_client(request, email_type, invoice_id):
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
    notify_method = request.POST.get("notify_method", "")
    methods = notify_method.split(",")

    messages_list = []

    if 'email' in methods:
        email_result = send_reminder_email(...)
        messages_list.append(email_result)

    if 'whatsapp' in methods:
        messages_list.append("WhatsApp sent")

    messages.success(request, " | ".join(messages_list))

    return redirect('invoice_list')

def confirm_termination(request, token):
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

    already = tracker.confirmation_response == "yes"

    return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": already, "accepted": False})

def accept_termination(request, token):
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
        return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": True, "accepted": False})

    
    tracker.confirmation_response = "yes"
    tracker.responded_at = timezone.now()
    tracker.confirmation_token = None
    tracker.save()

    Notification.objects.create(
        invoice=tracker.invoice,
        message=f"Client confirmed termination for invoice {tracker.invoice.id}.",
        type="action"
    )

    return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": False, "accepted": True})

@login_required
def notification_list(request):
    notifications = Notification.objects.order_by('-created_at')
    Notification.objects.filter(is_read=False).update(is_read=True)

    return render(request, 'notification_list.html', {
        'notifications': notifications
    })

def render_template(template_obj, data):
    subject_template = Template(template_obj.subject)
    body_template = Template(template_obj.body)

    context = Context(data)

    subject = subject_template.render(context)
    body = body_template.render(context)

    return subject, body

def template_list(request):
    templates = MessageTemplate.objects.all()
    return render(request, "template_list.html", {"templates": templates})

def custom_404(request, exception):
    if not request.user.is_authenticated:
        return redirect('login')
    return redirect('invoice_list')

def is_trainee(user):
    return user.groups.filter(name='Trainee').exists()

def is_billing(user):
    return user.groups.filter(name='Billing').exists()

def is_admin(user):
    return user.is_superuser or user.groups.filter(name='Admin').exists()


def can_edit_email(user):
    return is_billing(user) or is_admin(user)


def can_send_action(user, action):
    if is_admin(user) or is_billing(user):
        return True

    if is_trainee(user):
        return action == "suspension"

    return False