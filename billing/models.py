from django.db import models
from django.contrib.auth.models import User, Group

class GroupPermission(models.Model):
    ACTION_CHOICES = [
        ('send_suspension', 'Send Suspension Email'),
        ('send_confirmation', 'Send Confirmation Email'),
        ('send_queue', 'Send Queue Email'),
        ('send_termination', 'Send Termination Email'),
        ('edit_email_body', 'Edit Email Body Before Sending'),
        ('view_notifications', 'View Notifications'),
        ('receive_action_notifications', 'Receive Action Notifications'),
        ('receive_warning_notifications', 'Receive Warning Notifications'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='billing_permissions')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)

    class Meta:
        unique_together = ('group', 'action')

    def __str__(self):
        return f"{self.group.name} {self.action}"


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
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="tracker"
    )

    suspension_sent = models.BooleanField(default=False)
    suspension_sent_at = models.DateTimeField(null=True, blank=True)

    confirmation_sent = models.BooleanField(default=False)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    confirmation_expires_at = models.DateTimeField(null=True, blank=True)

    queue_sent = models.BooleanField(default=False)
    queue_sent_at = models.DateTimeField(null=True, blank=True)

    termination_sent = models.BooleanField(default=False)
    termination_sent_at = models.DateTimeField(null=True, blank=True)

    confirmation_response = models.CharField(max_length=10, null=True, blank=True)
    confirmation_token = models.CharField(max_length=100, blank=True, null=True)

    responded_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_verified = models.BooleanField(default=False)

    def __str__(self):
        return str(self.invoice.id)
    
class Notification(models.Model):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("action", "Action Required"),
        ("success", "Success"),
    ]

    target_groups = models.ManyToManyField(Group, blank=True)

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.invoice.id} - {self.message[:30]}"
    
class NotificationRead(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('notification', 'user')

    def __str__(self):
        return f"{self.user} read {self.notification.id}"

class EmailLog(models.Model):
    ticket = models.CharField(max_length=15, unique=True, null=True, blank=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default="pending")
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)

    def __str__(self):
        return f"{self.invoice.id} - {self.email_type}"
    
class EmailTemplate(models.Model):
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