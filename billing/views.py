from collections import defaultdict
import json
from sys import stdout
import uuid

from django.contrib import messages

from django.shortcuts import get_object_or_404, redirect, render

from django.template import Context, Template

from django.utils import timezone

from django.core.paginator import Paginator

from billing.services.api import get_invoices, get_invoice_details
from billing.services.email_service import send_reminder_email

from billing.models import ActionTracker, Invoice, MessageTemplate, Notification
from billing.services.api import get_invoices, get_invoice_details
from billing.services.email_service import send_reminder_email

from django.views.decorators.http import require_POST


def invoice_list(request):
    filter_status = request.GET.get('status')
    search_query = request.GET.get('search')

    invoices = Invoice.objects.select_related('client').prefetch_related('items')

    enriched = []

    trackers = { t.invoice_id: t for t in ActionTracker.objects.all()}

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

        if not tracker.confirmation_token:
            tracker.confirmation_token = str(uuid.uuid4())
            tracker.save()

        if not tracker:
            tracker = ActionTracker.objects.create(invoice_id=invoice.id)
            trackers[invoice.id] = tracker

        invoice.suspension_sent = tracker.suspension_sent
        invoice.termination_sent = tracker.termination_sent
        invoice.confirmation_sent = tracker.confirmation_sent
        invoice.queue_sent = tracker.queue_sent
        invoice.confirmation_token = tracker.confirmation_token or ""

        client = invoice.client

        invoice.name = str(client)
        invoice.email = client.email
        invoice.amount = invoice.total

        if invoice.status == "Paid":
            invoice.display_status = "paid"
        elif tracker.termination_sent:
            invoice.display_status = "terminated"
        elif tracker.suspension_sent:
            invoice.display_status = "suspended"
        else:
            invoice.display_status = "unpaid"

        if filter_status and invoice.display_status != filter_status:
            continue

        if search_query and search_query.lower() not in (str(invoice.id).lower() + (invoice.name or "").lower()):
            continue

        item = invoice.items.first()

        invoice.domain = item.domain_name if item else ""
        invoice.plan = item.plan_name if item else ""
        invoice.service = item.item_type if item else ""

        enriched.append(invoice)

    paginator = Paginator(enriched, 10)

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "invoice_list.html", {
        "page_obj": page_obj,
        "templates_json": json.dumps(grouped_templates, ensure_ascii=False)
    })

def send_email(request, email_type, invoice_id):
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

    result = send_reminder_email(
        invoice_id=invoice_id, 
        recipient_email=client.email,
        email_type=email_type,
        subject=subject,
        body=body
    )

    messages.success(request, result)

    return redirect('invoice_list')

def confirm_termination(request, token):
    tracker = get_object_or_404(ActionTracker, confirmation_token=token)

    already = tracker.confirmation_response == "yes"

    return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": already, "accepted": False})

def accept_termination(request, token):
    if request.method != "POST":
        return redirect('confirm_termination', token=token)
    
    tracker = get_object_or_404(ActionTracker, confirmation_token=token)

    if tracker.confirmation_response == "yes":
        return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": True, "accepted": False})

    
    tracker.confirmation_response = "yes"
    tracker.responded_at = timezone.now()
    tracker.save()

    Notification.objects.create(
        invoice_id=tracker.invoice_id,
        message=f"Client confirmed termination for invoice {tracker.invoice_id}.",
        type="action"
    )

    return render(request, "confirmation_response.html", {"tracker": tracker, "token": token, "already": False, "accepted": True})

def notification_list(request):
    db_notification = Notification.objects.select_related('invoice').order_by('-created_at')
    return render(request, "notification_list.html", {
        "notifications": db_notification,
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

def add_template(request):
    if request.method == "POST":
        name = request.POST.get("name")
        template_type = request.POST.get("template_type")
        subject = request.POST.get("subject")
        body = request.POST.get("body")

        MessageTemplate.objects.create(
            name=name,
            subject=subject,
            template_type=template_type,
            body=body
        )

        messages.success(request, "Template created successfully")
        return redirect("template_list")

    return render(request, "template_form.html", {
        "template": None,
        "mode": "add",
        "types": MessageTemplate.TEMPLATE_TYPES
    })

def edit_template(request, template_type):
    template = get_object_or_404(MessageTemplate, template_type=template_type)

    if request.method == "POST":
        template.name = request.POST.get("name")
        template.subject = request.POST.get("subject")
        template.body = request.POST.get("body")
        template.save()

        messages.success(request, "Template updated successfully")
        return redirect("template_list")

    return render(request, "template_form.html", {
        "template": template,
        "mode": "edit"
    })

@require_POST
def delete_template(request, id):
    template = get_object_or_404(MessageTemplate, id=id)

    template.delete()
    messages.success(request, "Template deleted successfully")

    return redirect("template_list")