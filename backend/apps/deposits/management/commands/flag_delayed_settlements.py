from django.core.management.base import BaseCommand

from apps.core.money import ZERO
from apps.deposits.services import flag_delayed_settlements


class Command(BaseCommand):
    help = "Audit deposits pending settlement beyond the SLA. Safe to run repeatedly in a day."

    def handle(self, *args, **options):
        flagged = flag_delayed_settlements()
        total = sum((deposit.deposited_amount for deposit in flagged), ZERO)
        self.stdout.write(
            self.style.SUCCESS(f"Flagged {len(flagged)} delayed settlement(s) worth {total}.")
        )
