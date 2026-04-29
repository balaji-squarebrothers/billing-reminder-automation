from datetime import timedelta
import uuid

# from django.contrib.sites.models import Site

from django.db import IntegrityError
from django.utils import timezone

from billing.models import ActionTracker, EmailLog

from django.conf import settings
from django.urls import reverse

from django.core.mail import EmailMessage

import random
import string
import logging

logger = logging.getLogger("billing")

TEST_TO_MAIL = 'testbybala.2005@gmail.com'

def generate_otp():
    return str(random.randint(100000, 999999))

def generate_ticket():
    letters = ''.join(random.choices(string.ascii_uppercase, k=3))
    numbers1 = ''.join(random.choices(string.digits, k=3))
    numbers2 = ''.join(random.choices(string.digits, k=5))

    return f"{letters}-{numbers1}-{numbers2}"

def createEmailLogObject(invoice, email_type, sent_by, retries=5):
    for _ in range(retries):
        try:
            ticket = generate_ticket()
            return EmailLog.objects.create(
                invoice=invoice,
                email_type=email_type,
                ticket=ticket,
                status="pending",
                sent_by=sent_by
            )
        except IntegrityError:
            continue
    raise Exception("Failed to generate unique ticket")

def send_otp_email(tracker):
    otp = generate_otp()
    tracker.otp_code = otp
    tracker.otp_expires_at = timezone.now() + timedelta(minutes=10)
    tracker.otp_verified = False
    tracker.save()

    try:
        email = EmailMessage(
            subject="Your Termination Confirmation OTP",
            body=f"""
                <p>You requested to confirm termination for invoice <strong>{tracker.invoice.id}</strong>.</p>
                <p>Your OTP is: <strong style="font-size:1.5rem; letter-spacing:0.3rem">{otp}</strong></p>
                <p>This OTP is valid for <strong>10 minutes</strong>.</p>
                <p>If you did not request this, please ignore this email.</p>
            """,
            # to=[tracker.invoice.client.email]
            to=[TEST_TO_MAIL]
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)

        logger.info(
            "Otp sent",
            extra={
                'otp_expires_at': tracker.otp_expires_at,
                'otp_verified': tracker.otp_verified,
            }
        )

    except Exception as e:
        logger.error(
            "Otp sending failed",
        )

def send_reminder_email(invoice, recipient_email, email_type, subject, body, include_confirm_link=False, sent_by_id=None):
        tracker, _ = ActionTracker.objects.get_or_create(invoice=invoice)

        sent_by = None
        if sent_by_id:
            from django.contrib.auth.models import User
            sent_by = User.objects.filter(id=sent_by_id).first()

        if email_type == "confirmation":
            if tracker.confirmation_response == "yes":
                logger.info(
                    "Already termination confirmed",
                    extra={
                        "invoice_id": invoice.id,
                    }
                )

            if tracker.confirmation_expires_at and tracker.confirmation_expires_at > timezone.now():
                logger.info(
                    "Confirmation already active",
                    extra={
                        "invoice_id": invoice.id
                    }
                )
        else:
            if EmailLog.objects.filter(invoice=invoice, email_type=email_type, status='sent').exists():
                logger.error(
                    "Email already sent",
                    extra={
                        "invoice_id": invoice.id,
                        "email_type": email_type,
                    }
                )
                return
        
        
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

        emailLog = createEmailLogObject(invoice=invoice, email_type=email_type, sent_by=sent_by)

        subject = f"[{emailLog.ticket}] {subject}"
        body += f"<br><br><strong>Ticket ID: {emailLog.ticket}</strong>"

        try:
            email = EmailMessage(
                subject=subject,
                body=body,
                # to=[recipient_email],
                to=[TEST_TO_MAIL]
            )
            email.content_subtype = "html"
            email.send(fail_silently=False)

            emailLog.status = "sent"
            emailLog.save()

        except Exception as e:
            emailLog.status = "failed"
            emailLog.retry_count += 1
            emailLog.last_error = str(e)
            emailLog.save()

            logger.error(
                "Email sending failed",
                extra={
                    "invoice_id": invoice.id,
                    "email_type": email_type,
                    "retry_count": emailLog.retry_count,
                }
            )

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

        
        logger.info(
            "Email sent and saved to ActionTracker",
            extra={
                "invoice_id": invoice.id,
                "email_type": email_type,
                "ticket": emailLog.ticket,
            }
        )