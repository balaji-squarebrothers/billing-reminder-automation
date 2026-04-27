from datetime import date, timedelta

from django.core.management.base import BaseCommand

from billing.models import Client, Invoice, InvoiceItem


class Command(BaseCommand):
    help = "Seed dummy data for development and testing"

    def handle(self, *args, **kwargs):
        self.seed_clients()
        self.seed_invoices()
        self.seed_invoice_items()

    def seed_clients(self):
        Client.objects.update_or_create(
            id="1001",
            defaults={
                "firstname": "Balaji",
                "lastname": "Selvam",
                "email": "balajiselvam0201@gmail.com",
                "phonenumber": "+91 9876543210",
            }
        )
        Client.objects.update_or_create(
            id="1002",
            defaults={
                "firstname": "Test",
                "lastname": "User",
                "email": "balajiselvam0201@gmail.com",
                "phonenumber": "+91 9000000000",
            }
        )
        Client.objects.update_or_create(
            id="1003",
            defaults={
                "firstname": "Square Brothers Info Tech",
                "lastname": "",
                "email": "balajiselvam0201@gmail.com",
                "phonenumber": "+91 9360303099",
            }
        )
        self.stdout.write(self.style.SUCCESS("✅ Clients seeded"))

    def seed_invoices(self):
        today = date.today()

        Invoice.objects.update_or_create(
            id="9001",
            defaults={
                "status": "Unpaid",
                "client": self._client("1001"),
                "date": today,
                "duedate": today + timedelta(days=7),
                "total": 1500,
            }
        )
        Invoice.objects.update_or_create(
            id="9002",
            defaults={
                "status": "Unpaid",
                "client": self._client("1002"),
                "date": today,
                "duedate": today,           # due today
                "total": 2500,
            }
        )
        Invoice.objects.update_or_create(
            id="9003",
            defaults={
                "status": "Unpaid",
                "client": self._client("1003"),
                "date": today - timedelta(days=10),
                "duedate": today - timedelta(days=3),   # overdue
                "total": 5000,
            }
        )
        Invoice.objects.update_or_create(
            id="9004",
            defaults={
                "status": "Paid",
                "client": self._client("1001"),
                "date": today - timedelta(days=30),
                "duedate": today - timedelta(days=20),
                "total": 800,
            }
        )
        self.stdout.write(self.style.SUCCESS("✅ Invoices seeded"))

    def seed_invoice_items(self):
        InvoiceItem.objects.update_or_create(
            invoice=self._invoice("9001"),
            defaults={
                "item_type": "Hosting",
                "description": "WR-25 - balaji.com (Hosting Plan)",
                "amount": 1500,
                "domain_name": "balaji.com",
                "plan_name": "WR-25",
            }
        )
        InvoiceItem.objects.update_or_create(
            invoice=self._invoice("9002"),
            defaults={
                "item_type": "SSL",
                "description": "SSL Certificate - test.com",
                "amount": 2500,
                "domain_name": "test.com",
                "plan_name": "SSL Certificate",
            }
        )
        InvoiceItem.objects.update_or_create(
            invoice=self._invoice("9003"),
            defaults={
                "item_type": "VPS",
                "description": "VPS Basic - squarebros.com",
                "amount": 5000,
                "domain_name": "squarebros.com",
                "plan_name": "VPS Basic",
            }
        )
        InvoiceItem.objects.update_or_create(
            invoice=self._invoice("9004"),
            defaults={
                "item_type": "Domain",
                "description": "Domain Registration - balaji.in",
                "amount": 800,
                "domain_name": "balaji.in",
                "plan_name": "Domain Registration",
            }
        )
        self.stdout.write(self.style.SUCCESS("✅ Invoice items seeded"))

    def _client(self, client_id):
        from billing.models import Client
        return Client.objects.get(id=client_id)

    def _invoice(self, invoice_id):
        from billing.models import Invoice
        return Invoice.objects.get(id=invoice_id)