from datetime import date, datetime

from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from billing.models import EmailLog
from billing.services.api import get_invoices, get_invoice_details
from billing.services.email_service import send_reminder_email


class Command(BaseCommand):
    
    def handle(self, *args, **options):
        today = date.today()

        RULES = {
            7: ('reminder_7', '7 days to go'),
            1: ('reminder_1', '1 days to go'),
            0: ('due_today', 'Due today'),
        }

        invoices = get_invoices()

        for invoice in invoices:
            invoice_id = invoice["id"]
            due_date = datetime.strptime(invoice["duedate"], "%Y-%m-%d").date()
            status = invoice["status"]

            if status == 'Paid':
                self.stdout.write(f"Client has already paid for the invoice {invoice_id}")
                continue

            days_to_due = (due_date - today).days

            if days_to_due not in RULES:
                self.stdout.write("")
                continue

            email_type, subject = RULES[days_to_due]

            details = get_invoice_details(invoice_id= invoice_id)
            
            if not details:
                self.stdout.write("Error fetching details")
                continue

            invoice_data = details.get("invoice", {})

            if invoice_data.get("status") == "Paid":
                self.stdout.write(f"Client has already paid for the invoice {invoice_id}")
                continue

            client = invoice_data.get("client")

            email = client.get("email")

            client_name = f"{client.get('firstname', '')} {client.get('lastname', '')}"
            result = send_reminder_email(invoice_id=invoice_id, email=email, email_type=email_type, subject=subject, client_name=client_name)

            self.stdout.write(result)