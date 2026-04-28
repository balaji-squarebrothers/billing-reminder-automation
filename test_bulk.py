import os
import django
import random
from datetime import date, timedelta
from decimal import Decimal

print("STEP 1")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "billing_reminder.settings")
print("STEP 2")
django.setup()
print("STEP 3")

from billing.models import Client, Invoice, InvoiceItem, ActionTracker


TOTAL = 100  # change to 500 / 1000 for stress test

print(f"Creating {TOTAL} invoices...")

today = date.today()

for i in range(TOTAL):
    # -------------------------
    # Create Client
    # -------------------------
    client_id = f"C{i}"

    client, _ = Client.objects.get_or_create(
        id=client_id,
        defaults={
            "firstname": f"Client{i}",
            "lastname": "Test",
            "email": f"test{i}@mail.com",
            "phonenumber": f"90000000{i%10}"
        }
    )

    # -------------------------
    # Random due date scenarios
    # -------------------------
    due_type = random.choice(["past", "today", "tomorrow"])

    if due_type == "past":
        duedate = today - timedelta(days=random.randint(1, 5))
    elif due_type == "today":
        duedate = today
    else:
        duedate = today + timedelta(days=1)

    # -------------------------
    # Create Invoice
    # -------------------------
    invoice = Invoice.objects.create(
        id=f"INV{i}",
        status="Unpaid",
        client=client,
        date=today - timedelta(days=random.randint(1, 10)),
        duedate=duedate,
        total=Decimal(random.randint(100, 1000)),
        notes="Test invoice"
    )

    # -------------------------
    # Create Invoice Item
    # -------------------------
    InvoiceItem.objects.create(
        invoice=invoice,
        item_type=random.choice(["Hosting", "Domain", "VPS"]),
        description="Test service",
        amount=invoice.total,
        domain_name=f"site{i}.com",
        plan_name=random.choice(["Basic", "Pro", "Enterprise"])
    )

    # -------------------------
    # Create ActionTracker
    # -------------------------
    tracker = ActionTracker.objects.create(invoice=invoice)

    # Simulate some previous actions (for follow-up testing)
    if random.choice([True, False]):
        tracker.suspension_sent = True
        tracker.suspension_sent_at = django.utils.timezone.now() - timedelta(days=6)

    if random.choice([True, False]):
        tracker.confirmation_sent = True
        tracker.confirmation_sent_at = django.utils.timezone.now() - timedelta(days=6)

    tracker.save()

print("✅ Test data created successfully!")