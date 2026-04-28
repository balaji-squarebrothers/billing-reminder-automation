from datetime import date, datetime
import time

from django.core.management.base import BaseCommand
from django.core.mail import send_mail

from billing.services.automation import retry_failed_emails, run_automation


class Command(BaseCommand):
    help = "Run automation tasks"
    
    def handle(self, *args, **options):
        self.stdout.write("Running automation...")
        start = time.time()

        run_automation()

        print("Time:", time.time() - start)
        retry_failed_emails()

        self.stdout.write(self.style.SUCCESS("DONE"))