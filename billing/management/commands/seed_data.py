# billing/management/commands/seed_data.py

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Client, Invoice, InvoiceItem, ActionTracker


class Command(BaseCommand):
    help = "Seed dummy data for development and testing"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.seed_clients()
        self.seed_invoices()
        self.seed_invoice_items()
        self.create_trackers()

        self.stdout.write(self.style.SUCCESS("🎉 Seeding completed"))

    def seed_clients(self):
        clients = [
            ("1001", "Balaji", "Selvam"),
            ("1002", "Test", "User"),
            ("1003", "Square Brothers Info Tech", ""),
        ]

        for cid, fname, lname in clients:
            Client.objects.update_or_create(
                id=cid,
                defaults={
                    "firstname": fname,
                    "lastname": lname,
                    "email": f"client{cid}@example.com",  # ✅ unique emails
                    "phonenumber": "+91 9000000000",
                }
            )

        self.stdout.write(self.style.SUCCESS("✅ Clients seeded"))

    def seed_invoices(self):
        today = date.today()

        data = [
            ("9001", "1001", "Unpaid", today, today + timedelta(days=7), 1500),
            ("9002", "1002", "Unpaid", today, today, 2500),
            ("9003", "1003", "Unpaid", today - timedelta(days=10), today - timedelta(days=3), 5000),
            ("9004", "1001", "Paid", today - timedelta(days=30), today - timedelta(days=20), 800),
        ]

        clients = {c.id: c for c in Client.objects.all()}

        for iid, cid, status, d, due, total in data:
            Invoice.objects.update_or_create(
                id=iid,
                defaults={
                    "status": status,
                    "client": clients.get(cid),
                    "date": d,
                    "duedate": due,
                    "total": Decimal(total),
                }
            )

        self.stdout.write(self.style.SUCCESS("✅ Invoices seeded"))

    def seed_invoice_items(self):
        invoices = {i.id: i for i in Invoice.objects.all()}

        items = [
            ("9001", "Hosting", "WR-25 - balaji.com", 1500, "balaji.com", "WR-25"),
            ("9002", "SSL", "SSL Certificate - test.com", 2500, "test.com", "SSL Certificate"),
            ("9003", "VPS", "VPS Basic - squarebros.com", 5000, "squarebros.com", "VPS Basic"),
            ("9004", "Domain", "Domain Registration - balaji.in", 800, "balaji.in", "Domain Registration"),
        ]

        for inv_id, item_type, desc, amt, domain, plan in items:
            InvoiceItem.objects.update_or_create(
                invoice=invoices.get(inv_id),
                description=desc,
                defaults={
                    "item_type": item_type,
                    "amount": Decimal(amt),
                    "domain_name": domain,
                    "plan_name": plan,
                }
            )

        self.stdout.write(self.style.SUCCESS("✅ Invoice items seeded"))

    def create_trackers(self):
        for invoice in Invoice.objects.all():
            ActionTracker.objects.get_or_create(invoice=invoice)

        self.stdout.write(self.style.SUCCESS("✅ ActionTrackers created"))