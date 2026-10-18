from django.core.management.base import BaseCommand

from apps.payments.services import expire_stale_orders


class Command(BaseCommand):
    help = "Expire UPI orders with no payment attempt past the checkout window. Idempotent."

    def handle(self, *args, **options):
        expired = expire_stale_orders()
        self.stdout.write(self.style.SUCCESS(f"Expired {len(expired)} unpaid UPI order(s)."))
