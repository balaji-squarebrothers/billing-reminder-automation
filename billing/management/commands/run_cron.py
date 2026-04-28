from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from billing.models import EmailLog
from billing.services.api import get_invoices, get_invoice_details
from billing.services.email_service import send_reminder_email


class Command(BaseCommand):
    
    def handle(self, *args, **options):
        