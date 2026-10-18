import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Count

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.branches.models import Branch
from apps.collections.models import Collection
from apps.core.management.demo import data
from apps.core.management.demo.reset import wipe_data
from apps.core.management.demo.seeder import DemoSeeder, is_seeded
from apps.customers.models import Customer
from apps.deposits.models import BankDeposit
from apps.loans.models import Installment, Loan
from apps.payments.models import GatewayOrder
from apps.reconciliation.models import CashSubmission, Discrepancy

DEFAULT_SEED = 2026
STATUS_MODELS = (
    ("Loans", Loan),
    ("Installments", Installment),
    ("Collections", Collection),
    ("Cash submissions", CashSubmission),
    ("Bank deposits", BankDeposit),
    ("Discrepancies", Discrepancy),
    ("Gateway orders", GatewayOrder),
)


class Command(BaseCommand):
    help = (
        "Load a realistic demo dataset: three branches, their staff and borrowers, and a few "
        "months of collections, hand-overs, deposits and settlements replayed through the "
        "services. Does nothing if the demo data is already present."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete ALL CashTrail data before seeding. Irreversible.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"Random seed (default {DEFAULT_SEED}); a seed always yields the same data "
            "relative to the day it runs.",
        )
        parser.add_argument(
            "--no-input",
            "--noinput",
            action="store_false",
            dest="interactive",
            help="Do not ask for confirmation before --reset.",
        )

    def handle(self, *args, reset: bool, seed: int, interactive: bool, **options):
        if reset and interactive and sys.stdin.isatty():
            database = connection.settings_dict["NAME"]
            answer = input(f"This deletes ALL CashTrail data in '{database}'. Type 'yes': ")
            if answer.strip().lower() != "yes":
                raise CommandError("Reset cancelled.")

        with transaction.atomic():
            if reset:
                wipe_data()
            elif is_seeded():
                self.stdout.write(
                    self.style.WARNING("Demo data is already loaded; use --reset to rebuild it.")
                )
                self._print_credentials()
                return
            DemoSeeder(seed=seed).run()

        self.stdout.write(self.style.SUCCESS(f"Demo data loaded (seed {seed})."))
        self._print_summary()
        self._print_credentials()

    def _print_summary(self) -> None:
        rows = [
            ("Branches", Branch.objects.count(), ""),
            ("Users", User.objects.count(), ""),
            ("Customers", Customer.objects.count(), ""),
        ]
        for label, model in STATUS_MODELS:
            counts = dict(
                model.objects.order_by().values_list("status").annotate(total=Count("pk"))
            )
            breakdown = ", ".join(
                f"{status} {counts[status]}" for status in model.Status.values if status in counts
            )
            rows.append((label, sum(counts.values()), breakdown))
        rows.append(("Audit log entries", AuditLog.objects.count(), ""))
        self._print_table(("Records", "Count", "By status"), rows)

    def _print_credentials(self) -> None:
        roles = dict(User.Role.choices)
        rows = [
            (
                staff.username,
                roles[staff.role],
                staff.branch_code or "All branches",
                f"{staff.first_name} {staff.last_name}",
            )
            for staff in data.STAFF
        ]
        self._print_table(("Username", "Role", "Branch", "Name"), rows)
        self.stdout.write(f"Every demo user signs in with the password {data.DEMO_PASSWORD}\n")

    def _print_table(self, header: tuple[str, ...], rows: list[tuple]) -> None:
        cells = [header, *[tuple(str(value) for value in row) for row in rows]]
        widths = [max(len(row[i]) for row in cells) for i in range(len(header))]
        lines = [
            "  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)).rstrip()
            for row in cells
        ]
        lines.insert(1, "  ".join("-" * width for width in widths))
        self.stdout.write("\n" + "\n".join(lines) + "\n")
