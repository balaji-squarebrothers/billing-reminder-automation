import time

from datetime import timedelta
from django.core.mail import EmailMessage
from django.utils import timezone
from django.template import Context, Template

from billing.models import ActionTracker, EmailLog, Invoice, MessageTemplate, Notification
from billing.services.email_service import send_reminder_email


DUE_TOMORROW = "due_tomorrow"
DUE_TODAY = "due_today"

ACTION = "action"
WARNING = "warning"


def render_template(template_obj, data):
    subject = Template(template_obj.subject).render(Context(data))
    body = Template(template_obj.body).render(Context(data))
    return subject, body

def already_sent(invoice, email_type):
    return EmailLog.objects.filter(
        invoice=invoice,
        email_type=email_type,
        status="sent"
    ).exists()


def run_automation():
    today = timezone.now().date()

    invoices = Invoice.objects.select_related('client').prefetch_related('items').filter(status__in=['unpaid', 'overdue'])

    invoice_ids = [inv.id for inv in invoices]

    trackers = {
        t.invoice_id: t
        for t in ActionTracker.objects.filter(invoice_id__in=invoice_ids)
    }

    sent_logs = set(
        EmailLog.objects.filter(
            invoice_id__in=invoice_ids,
            status="sent"
        ).values_list('invoice_id', 'email_type')
    )
    

    templates = {
        t.template_type: t
        for t in MessageTemplate.objects.filter(is_active=True)
    }

    from concurrent.futures import ThreadPoolExecutor

    email_jobs = []

    for invoice in invoices:
        tracker = trackers.get(invoice.id)

        if not tracker:
            tracker = ActionTracker.objects.create(invoice=invoice)

        item = invoice.items.first()

        data = {
            "client_name": str(invoice.client),
            "invoice_id": invoice.id,
            "amount": invoice.total,
            "due_date": invoice.duedate,
            "domain": item.domain_name if item else "",
            "plan": item.plan_name if item else "",
            "service": item.item_type if item else "",
        }

        if invoice.duedate == today + timedelta(days=1) and (invoice.id, DUE_TOMORROW) not in sent_logs:
            template = templates.get(DUE_TOMORROW)
            if template:
                subject, body = render_template(template, data)

                email_jobs.append({
                    "invoice": invoice,
                    "email_type": DUE_TOMORROW,
                    "recipient_email": invoice.client.email,
                    "subject": subject,
                    "body": body,
                })

        if invoice.duedate == today and (invoice.id, DUE_TODAY) not in sent_logs:
            template = templates.get(DUE_TODAY)
            if template:
                subject, body = render_template(template, data)

                email_jobs.append({
                    "invoice": invoice,
                    "email_type": DUE_TODAY,
                    "recipient_email": invoice.client.email,
                    "subject": subject,
                    "body": body,
                })

        if invoice.duedate < today and not tracker.suspension_sent:
            Notification.objects.get_or_create(
                invoice=invoice,
                message=f"Invoice {invoice.id} overdue. Send suspension.",
                type=ACTION
            )

        if tracker.suspension_sent and tracker.suspension_sent_at:
            if tracker.suspension_sent_at + timedelta(days=5) <= timezone.now() and not tracker.confirmation_sent:
                Notification.objects.get_or_create(
                    invoice=invoice,
                    message=f"5 days passed since suspension for {invoice.id}. Send confirmation.",
                    type=WARNING
                )

        if tracker.confirmation_sent and tracker.confirmation_sent_at:
            if tracker.confirmation_sent_at + timedelta(days=5) <= timezone.now() and not tracker.queue_sent:
                Notification.objects.get_or_create(
                    invoice=invoice,
                    message=f"5 days passed since confirmation for {invoice.id}. Send queue.",
                    type=WARNING
                )

        if tracker.queue_sent and tracker.queue_sent_at:
            if tracker.queue_sent_at + timedelta(days=5) <= timezone.now() and not tracker.termination_sent:
                Notification.objects.get_or_create(
                    invoice=invoice,
                    message=f"5 days passed since queue for {invoice.id}. Send termination.",
                    type=WARNING
                )

    BATCH_SIZE = 20

    def send_job(job):
        send_reminder_email(
            invoice=job["invoice"],
            email_type=job["email_type"],
            recipient_email=job["recipient_email"],
            subject=job["subject"],
            body=job["body"]
        )

    for i in range(0, len(email_jobs), BATCH_SIZE):
        batch = email_jobs[i:i+BATCH_SIZE]

        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(send_job, batch)

        time.sleep(2)

def retry_failed_emails():
    failed_logs = EmailLog.objects.select_related('invoice__client').filter(
        status="failed",
        retry_count__lt=3
    ).iterator(chunk_size=20)

    for log in failed_logs:
        invoice = log.invoice

        template = MessageTemplate.objects.filter(
            template_type=log.email_type,
            is_active=True
        ).first()

        if not template:
            continue

        data = {
            "client_name": str(invoice.client),
            "invoice_id": invoice.id,
            "amount": invoice.total,
        }

        subject, body = render_template(template, data)

        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                to=[invoice.client.email],
            )
            email.content_subtype = "html"
            email.send()

            log.status = "sent"
            log.save()

            time.sleep(0.2)

        except Exception as e:
            log.retry_count += 1
            log.last_error = str(e)
            log.save()