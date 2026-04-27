from django.utils import timezone

from billing.models import ActionTracker, EmailLog
from django.core.mail import send_mail, EmailMessage


def send_reminder_email(invoice_id, recipient_email, email_type, subject, body):
        tracker, _ = ActionTracker.objects.get_or_create(invoice_id=invoice_id)

        if EmailLog.objects.filter(invoice_id=invoice_id, email_type=email_type).exists():
            if email_type == "suspension":
                tracker.suspension_sent = True
            elif email_type == "confirmation":
                tracker.confirmation_sent = True
            elif email_type == "queue":
                tracker.queue_sent = True
            elif email_type == "termination":
                tracker.termination_sent = True

            tracker.save()
            return f"Already sent {email_type} for {invoice_id}"

        email = EmailMessage(
              subject=subject,
              body=body,
              to=['sajewi9828@hacknapp.com'],
        )
        email.send(fail_silently=False)

        EmailLog.objects.create(invoice_id=invoice_id, email_type=email_type)

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

        return f"Sent {email_type} for {invoice_id}"