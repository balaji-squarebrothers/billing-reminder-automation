# billing/management/commands/import_data.py

import csv
import re
from decimal import Decimal
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from billing.models import Client, Invoice, InvoiceItem, ActionTracker


def parse_date(value):
    if not value or value.strip().upper() == 'NULL':
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(value):
    if not value or value.strip().upper() == 'NULL':
        return Decimal("0")
    try:
        return Decimal(value.strip())
    except:
        return Decimal("0")


def extract_domain(description):
    if not description:
        return None
    match = re.search(r'-\s*([\w.-]+\.[a-z]{2,})', description, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_plan(description):
    if not description:
        return None
    match = re.match(r'^([\w\s-]+?)\s+-\s+', description.strip())
    return match.group(1).strip() if match else None


class Command(BaseCommand):
    help = "Import CSV data into DB"

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.import_clients()
        self.import_invoices()
        self.import_invoice_items()
        self.create_trackers()

        self.stdout.write(self.style.SUCCESS("🎉 Import completed"))

    def import_clients(self):
        count = 0

        with open('billing/data/hb_client_details.csv', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                company = row.get('companyname', '').strip()
                fname = row.get('firstname', '').strip()
                lname = row.get('lastname', '').strip()

                name = company if company else fname
                last = '' if company else lname

                email = row.get('email', '').strip()
                if not email or email.upper() == 'NULL':
                    email = f"client{row['id']}@example.com"

                Client.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        "firstname": name,
                        "lastname": last,
                        "email": email,
                        "phonenumber": row.get('phonenumber') or None,
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} clients imported"))

    def import_invoices(self):
        count, skipped = 0, 0

        clients = {c.id: c for c in Client.objects.all()}

        with open('billing/data/hb_invoices.csv', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                client = clients.get(row['client_id'])

                if not client:
                    skipped += 1
                    continue

                Invoice.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        "status": row.get('status', 'Unpaid'),
                        "client": client,
                        "date": parse_date(row.get('date')),
                        "duedate": parse_date(row.get('duedate')),
                        "total": parse_decimal(row.get('total')),
                        "notes": row.get('notes') or None,
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} invoices imported ({skipped} skipped)"))

    def import_invoice_items(self):
        count, skipped = 0, 0

        invoices = {i.id: i for i in Invoice.objects.all()}

        with open('billing/data/hb_invoice_items.csv', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                invoice = invoices.get(row['invoice_id'])

                if not invoice:
                    skipped += 1
                    continue

                desc = row.get('description', '').strip()

                InvoiceItem.objects.update_or_create(
                    invoice=invoice,
                    description=desc,
                    defaults={
                        "item_type": row.get('type') or None,
                        "amount": parse_decimal(row.get('amount')),
                        "domain_name": extract_domain(desc),
                        "plan_name": extract_plan(desc),
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} items imported ({skipped} skipped)"))

    def create_trackers(self):
        for invoice in Invoice.objects.all():
            ActionTracker.objects.get_or_create(invoice=invoice)

        self.stdout.write(self.style.SUCCESS("✅ ActionTrackers created"))