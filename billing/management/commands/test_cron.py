import time
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "billing_reminder.settings")
django.setup()

from billing.services.automation import run_automation, retry_failed_emails

while True:
    print("Running automation...")
    start = time.time()

    run_automation()

    print("Time:", time.time() - start)
    retry_failed_emails()

    print("Sleeping for 10 seconds...")
    time.sleep(10)