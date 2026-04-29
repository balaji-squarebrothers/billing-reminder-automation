import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

logger = logging.getLogger('billing')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, invoice_id, recipient_email, email_type, subject, body, include_confirm_link=False, sent_by_id=None):
    try:
        from billing.models import Invoice
        from billing.services.email_service import send_reminder_email
        
        invoice = Invoice.objects.select_related('client').get(id=invoice_id)

        logger.info("Sending email", extra={
            "invoice_id": invoice_id,
            "email_type": email_type,
            "recipient": recipient_email
        })

        result = send_reminder_email(
            invoice=invoice,
            email_type=email_type,
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            include_confirm_link=include_confirm_link,
            sent_by_id=sent_by_id
        )

        logger.info("Email sent successfully", extra={
            "invoice_id": invoice_id,
            "email_type": email_type
        })

        return result

    except Exception as exc:
        try:
            logger.error(
                "Email task failed, retrying",
                exc_info=True,
                extra={
                    "invoice_id": invoice_id,
                    "email_type": email_type
                }
            )
            raise self.retry(exc=exc)

        except MaxRetriesExceededError:
            logger.critical(
                "Max retries exceeded for email",
                exc_info=True,
                extra={
                    "invoice_id": invoice_id,
                    "email_type": email_type
                }
            )


@shared_task
def run_automation_task():
    try:
        logger.info("Automation task started")

        from billing.services.automation import run_automation
        run_automation()

        logger.info("Automation task completed")

    except Exception:
        logger.error("Automation task failed", exc_info=True)
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def retry_failed_emails_task(self):
    try:
        logger.info("Retry failed emails task started")

        from billing.services.automation import retry_failed_emails
        retry_failed_emails()

        logger.info("Retry failed emails task completed")

    except Exception as exc:
        logger.error(
            "Retry task failed",
            exc_info=True,
            extra={"task": "retry_failed_emails"}
        )
        raise self.retry(exc=exc)