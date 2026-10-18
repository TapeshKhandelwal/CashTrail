from django.core.management.base import BaseCommand

from apps.payments.services import sync_open_orders


class Command(BaseCommand):
    help = (
        "Ask the gateway about unpaid UPI orders from the last day and record payments whose "
        "webhook never arrived. Idempotent."
    )

    def handle(self, *args, **options):
        changed = sync_open_orders()
        self.stdout.write(self.style.SUCCESS(f"Updated {len(changed)} UPI order(s)."))
