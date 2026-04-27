import csv
import re
from datetime import datetime

from django.core.management.base import BaseCommand

from billing.models import Client, Invoice, InvoiceItem


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
        return 0
    try:
        return float(value.strip())
    except ValueError:
        return 0


def extract_domain(description):
    """
    Extract domain from descriptions like:
    'WR-25 - raghavanms.com (04/22/2011 - 05/21/2011)'
    'SSL Certificate - test.com'
    """
    if not description:
        return None
    match = re.search(r'-\s*([\w.-]+\.[a-z]{2,})', description, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_plan(description):
    """
    Extract plan code from descriptions like:
    'WR-25 - raghavanms.com ...'  → 'WR-25'
    'LR-10 - fisscal.com ...'     → 'LR-10'
    'SSL Certificate - test.com'  → 'SSL Certificate'
    """
    if not description:
        return None
    match = re.match(r'^([\w\s-]+?)\s+-\s+', description.strip())
    return match.group(1).strip() if match else None


class Command(BaseCommand):
    help = "Import CSV data into DB"

    def handle(self, *args, **kwargs):
        self.import_clients()
        self.import_invoices()
        self.import_invoice_items()

    def import_clients(self):
        self.stdout.write("Importing clients...")
        count = 0

        with open('billing/data/hb_client_details.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                companyname = row.get('companyname', '').strip()
                firstname = row.get('firstname', '').strip()
                lastname = row.get('lastname', '').strip()

                if companyname:
                    display_name = companyname
                    last = ''
                else:
                    display_name = firstname
                    last = lastname

                # Dummy email until real contacts table is available
                email = row.get('email', '').strip()
                if not email or email.upper() == 'NULL':
                    email = f"client{row['id']}@example.com"

                phonenumber = row.get('phonenumber', '').strip()
                if phonenumber.upper() == 'NULL':
                    phonenumber = None

                Client.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'firstname': display_name,
                        'lastname': last,
                        'email': email,
                        'phonenumber': phonenumber,
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} clients imported"))

    def import_invoices(self):
        self.stdout.write("Importing invoices...")
        count = 0
        skipped = 0

        with open('billing/data/hb_invoices.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                client = Client.objects.filter(id=row['client_id']).first()

                if not client:
                    skipped += 1
                    continue

                Invoice.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'status': row.get('status', 'Unpaid'),
                        'client': client,
                        'date': parse_date(row.get('date')),
                        'duedate': parse_date(row.get('duedate')),
                        'total': parse_decimal(row.get('total')),
                        'notes': row.get('notes', '') or None,
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} invoices imported ({skipped} skipped — client not found)"))

    def import_invoice_items(self):
        self.stdout.write("Importing invoice items...")
        count = 0
        skipped = 0

        with open('billing/data/hb_invoice_items.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                invoice = Invoice.objects.filter(id=row['invoice_id']).first()

                if not invoice:
                    skipped += 1
                    continue

                description = row.get('description', '').strip()
                item_type = row.get('type', '').strip() or None
                domain_name = extract_domain(description)
                plan_name = extract_plan(description)

                InvoiceItem.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'invoice': invoice,
                        'item_type': item_type,
                        'description': description,
                        'amount': parse_decimal(row.get('amount')),
                        'domain_name': domain_name,
                        'plan_name': plan_name,
                    }
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ {count} invoice items imported ({skipped} skipped — invoice not found)"))