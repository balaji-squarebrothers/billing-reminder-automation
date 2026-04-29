from datetime import timedelta
from django.utils import timezone
from django.template import Context, Template

from billing.models import (
    ActionTracker,
    EmailLog,
    EmailTemplate,
    Invoice,
    Notification
)

from billing.tasks import send_email_task


from celery.exceptions import MaxRetriesExceededError

import logging

logger = logging.getLogger("billing")


DUE_TOMORROW = "due_tomorrow"
DUE_TODAY = "due_today"

ACTION = "action"
WARNING = "warning"


def render_template(template_obj, data):
    subject = Template(template_obj.subject).render(Context(data))
    body = Template(template_obj.body).render(Context(data))
    return subject, body


def run_automation():
    today = timezone.now().date()

    invoices = Invoice.objects.select_related('client').prefetch_related('items')\
        .filter(status__in=['unpaid', 'overdue'])

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
        for t in EmailTemplate.objects.filter(is_active=True)
    }

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

                send_email_task.delay(
                    invoice_id=invoice.id,
                    email_type=DUE_TOMORROW,
                    recipient_email=invoice.client.email,
                    subject=subject,
                    body=body
                )

        if invoice.duedate == today and (invoice.id, DUE_TODAY) not in sent_logs:
            template = templates.get(DUE_TODAY)
            if template:
                subject, body = render_template(template, data)

                send_email_task.delay(
                    invoice_id=invoice.id,
                    email_type=DUE_TODAY,
                    recipient_email=invoice.client.email,
                    subject=subject,
                    body=body
                )

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


def retry_failed_emails():
    try:
        failed_logs = EmailLog.objects.select_related('invoice__client').filter(
            status="failed",
            retry_count__lt=3
        )

        templates = {
            t.template_type: t
            for t in EmailTemplate.objects.filter(is_active=True)
        }

        for log in failed_logs:
            invoice = log.invoice
            template = templates.get(log.email_type)

            if not template:
                continue

            data = {
                "client_name": str(invoice.client),
                "invoice_id": invoice.id,
                "amount": invoice.total,
            }

            subject, body = render_template(template, data)

            send_email_task.delay(
                invoice_id=invoice.id,
                email_type=log.email_type,
                recipient_email=invoice.client.email,
                subject=subject,
                body=body
            )

    except Exception as exc:
        try:
            logger.error(
                "Email task failed, retrying...",
                exc_info=True,
                extra={
                    "invoice_id": invoice.id,
                    "email_type": log.email_type
                }
            )
            raise self.retry(exc=exc)

        except MaxRetriesExceededError:
            logger.critical(
                "Max retries exceeded for email task",
                exc_info=True,
                extra={
                    "invoice_id": invoice.id,
                    "email_type": log.email_type
                }
            )