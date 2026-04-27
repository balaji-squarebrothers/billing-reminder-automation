from django.db import models


class Client(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    firstname = models.CharField(max_length=255)
    lastname = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(null=True, blank=True)
    phonenumber = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return self.firstname if not self.lastname else f"{self.firstname} {self.lastname}"


class Invoice(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    status = models.CharField(max_length=50)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='invoices')
    date = models.DateField(null=True, blank=True)
    duedate = models.DateField(null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.id


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    domain_name = models.CharField(max_length=255, null=True, blank=True)
    plan_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.invoice.id} - {self.item_type} - {self.domain_name or ''}"


class ActionTracker(models.Model):
    invoice_id = models.CharField(max_length=100, unique=True)

    suspension_sent = models.BooleanField(default=False)
    suspension_sent_at = models.DateTimeField(null=True, blank=True)

    confirmation_sent = models.BooleanField(default=False)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    queue_sent = models.BooleanField(default=False)
    queue_sent_at = models.DateTimeField(null=True, blank=True)

    termination_sent = models.BooleanField(default=False)
    termination_sent_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.invoice_id


class EmailLog(models.Model):
    invoice_id = models.CharField(max_length=100)
    email_type = models.CharField(max_length=50)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.CharField(max_length=100, default='system')

    def __str__(self):
        return f"{self.invoice_id} - {self.email_type}"
    
class MessageTemplate(models.Model):
    TEMPLATE_TYPES = [
        ("invoice_generated", "Invoice Generated"),
        ("due_tomorrow", "1 Day Before Due"),
        ("due_today", "Due Date"),
        ("suspension", "Suspension"),
        ("confirmation", "Confirmation"),
        ("queue", "Queue"),
        ("termination", "Termination"),
    ]

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)

    subject = models.TextField()
    body = models.TextField()

    is_active = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["template_type"]