from datetime import timedelta
import uuid

# from django.contrib.sites.models import Site

from django.utils import timezone

from billing.models import ActionTracker, EmailLog
from django.core.mail import send_mail

from django.conf import settings
from django.urls import reverse

from django.core.mail import EmailMessage

def send_reminder_email(invoice, recipient_email, email_type, subject, body, include_confirm_link=False):
        tracker, _ = ActionTracker.objects.get_or_create(invoice=invoice)

        if email_type == "confirmation":
            if tracker.confirmation_response == "yes":
                return f"Already confirmed for {invoice.id}"

            if tracker.confirmation_expires_at and tracker.confirmation_expires_at > timezone.now():
                return f"Confirmation already active for {invoice.id}"
        else:
            if EmailLog.objects.filter(invoice=invoice, email_type=email_type).exists():
                return f"Already sent {email_type} for {invoice.id}"
        
        
        if email_type == "confirmation" and include_confirm_link:
            tracker.confirmation_token = str(uuid.uuid4())
            tracker.confirmation_expires_at = timezone.now() + timedelta(days=2)
            tracker.confirmation_response = None

            path = reverse("confirm_termination", args=[tracker.confirmation_token])

            # domain = Site.objects.get_current().domain
            # confirmation_url = f"https://{domain}{path}"

            confirmation_url = f"{settings.BASE_URL}{path}"

            body += f"<br><br><a href='{confirmation_url}'>Confirm Termination</a>"

            tracker.save()

        log = EmailLog.objects.create(
            invoice=invoice,
            email_type=email_type,
            status="pending"
        )

        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                to=[recipient_email],
            )
            email.content_subtype = "html"
            email.send(fail_silently=False)

            log.status = "sent"
            log.save()

        except Exception as e:
            log.status = "failed"
            log.retry_count += 1
            log.last_error = str(e)
            log.save()

            return f"Failed {email_type} for {invoice.id}"

        if email_type == "suspension":
            tracker.suspension_sent = True
            tracker.suspension_sent_at = timezone.now()

        elif email_type == "confirmation":
            tracker.confirmation_sent = True
            tracker.confirmation_sent_at = timezone.now()

        elif email_type == "queue":
            tracker.queue_sent = True
            tracker.queue_sent_at = timezone.now()

        elif email_type == "termination":
            tracker.termination_sent = True
            tracker.termination_sent_at = timezone.now()

        tracker.save()

        return f"Sent {email_type} for {invoice.id}"