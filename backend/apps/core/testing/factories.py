"""factory_boy factories for every model.

Factories build rows that satisfy the database constraints, but they do not run
business workflows: use the services to move records through their lifecycle.
"""

import uuid
from decimal import Decimal

import factory
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog
from apps.branches.models import Branch
from apps.collections.models import Allocation, Collection
from apps.core.dates import business_date
from apps.customers.models import Customer
from apps.deposits.models import BankAccount, BankDeposit
from apps.loans.models import Installment, Loan
from apps.loans.schedule import generate_schedule
from apps.payments.models import GatewayOrder, GatewayProvider, WebhookEvent
from apps.reconciliation.models import CashSubmission, Discrepancy

DEFAULT_PASSWORD = "Test-pass-123!"


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"BR{n:03d}")
    name = factory.LazyAttribute(lambda o: f"Branch {o.code}")
    city = "Bengaluru"
    address = factory.Faker("street_address", locale="en_IN")


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    first_name = factory.Faker("first_name", locale="en_IN")
    last_name = factory.Faker("last_name", locale="en_IN")
    email = factory.LazyAttribute(lambda o: f"{o.username}@cashtrail.test")
    phone = factory.Sequence(lambda n: f"98{n:08d}")
    password = factory.django.Password(DEFAULT_PASSWORD)
    role = User.Role.AGENT
    branch = factory.Maybe(
        factory.LazyAttribute(lambda o: o.role in User.BRANCH_ROLES),
        yes_declaration=factory.SubFactory(BranchFactory),
        no_declaration=None,
    )


class AdminUserFactory(UserFactory):
    username = factory.Sequence(lambda n: f"admin{n}")
    role = User.Role.ADMIN
    is_staff = True
    is_superuser = True


class FinanceUserFactory(UserFactory):
    username = factory.Sequence(lambda n: f"finance{n}")
    role = User.Role.FINANCE


class BranchManagerFactory(UserFactory):
    username = factory.Sequence(lambda n: f"manager{n}")
    role = User.Role.BRANCH_MANAGER


class AgentFactory(UserFactory):
    username = factory.Sequence(lambda n: f"agent{n}")
    role = User.Role.AGENT


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer

    customer_code = factory.Sequence(lambda n: f"CUS-T{n:06d}")
    full_name = factory.Faker("name", locale="en_IN")
    phone = factory.Sequence(lambda n: f"97{n:08d}")
    address = factory.Faker("address", locale="en_IN")
    branch = factory.SubFactory(BranchFactory)
    assigned_agent = factory.SubFactory(AgentFactory, branch=factory.SelfAttribute("..branch"))


class LoanFactory(factory.django.DjangoModelFactory):
    """Creates the loan with its full EMI schedule (installments) from `generate_schedule`."""

    class Meta:
        model = Loan

    loan_number = factory.Sequence(lambda n: f"LN-T{n:06d}")
    customer = factory.SubFactory(CustomerFactory)
    branch = factory.SelfAttribute("customer.branch")
    principal = Decimal("100000.00")
    annual_interest_rate = Decimal("12.00")
    tenure_months = 12
    disbursed_on = factory.LazyFunction(lambda: business_date() - relativedelta(months=1))
    first_due_date = factory.LazyAttribute(lambda o: o.disbursed_on + relativedelta(months=1))

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        rows = generate_schedule(
            kwargs["principal"],
            kwargs["annual_interest_rate"],
            kwargs["tenure_months"],
            kwargs["first_due_date"],
        )
        kwargs.setdefault("emi_amount", rows[0].amount_due)
        kwargs.setdefault("total_payable", sum(row.amount_due for row in rows))
        loan = super()._create(model_class, *args, **kwargs)
        Installment.objects.bulk_create(
            Installment(
                loan=loan,
                installment_no=row.installment_no,
                due_date=row.due_date,
                principal_component=row.principal_component,
                interest_component=row.interest_component,
                amount_due=row.amount_due,
            )
            for row in rows
        )
        return loan


class InstallmentFactory(factory.django.DjangoModelFactory):
    """Standalone installment; prefer `LoanFactory`, which builds the whole schedule."""

    class Meta:
        model = Installment

    loan = factory.SubFactory(LoanFactory, tenure_months=1)
    installment_no = factory.Sequence(lambda n: n + 100)
    due_date = factory.LazyFunction(business_date)
    principal_component = Decimal("1000.00")
    interest_component = Decimal("100.00")
    amount_due = factory.LazyAttribute(lambda o: o.principal_component + o.interest_component)


class BankAccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BankAccount

    bank_name = "State Bank of India"
    account_name = "CashTrail Finance Pvt Ltd"
    account_number_last4 = factory.Sequence(lambda n: f"{n % 10000:04d}")
    ifsc = "SBIN0001234"

    class Params:
        gateway = factory.Trait(
            is_gateway=True, bank_name="Razorpay", account_name="Gateway settlements", ifsc=""
        )


_branch_reviewer = factory.SubFactory(
    BranchManagerFactory, branch=factory.SelfAttribute("..branch")
)


class CashSubmissionFactory(factory.django.DjangoModelFactory):
    """Pending submission by default; traits `approved`, `short` and `rejected` mark it reviewed."""

    class Meta:
        model = CashSubmission

    submission_number = factory.Sequence(lambda n: f"SUB-T{n:06d}")
    agent = factory.SubFactory(AgentFactory)
    branch = factory.SelfAttribute("agent.branch")
    expected_amount = Decimal("5000.00")
    declared_amount = factory.SelfAttribute("expected_amount")
    idempotency_key = factory.LazyFunction(uuid.uuid4)

    class Params:
        approved = factory.Trait(
            status=CashSubmission.Status.APPROVED,
            received_amount=factory.SelfAttribute("expected_amount"),
            reviewed_at=factory.LazyFunction(timezone.now),
            reviewed_by=_branch_reviewer,
        )
        short = factory.Trait(
            status=CashSubmission.Status.APPROVED_WITH_DISCREPANCY,
            received_amount=factory.LazyAttribute(lambda o: o.expected_amount - Decimal("500.00")),
            reviewed_at=factory.LazyFunction(timezone.now),
            reviewed_by=_branch_reviewer,
            review_remarks="Counted short.",
        )
        rejected = factory.Trait(
            status=CashSubmission.Status.REJECTED,
            reviewed_at=factory.LazyFunction(timezone.now),
            reviewed_by=_branch_reviewer,
            rejection_reason="Receipts and cash do not match.",
        )


def gateway_bank_account() -> BankAccount:
    """The single active gateway settlement account, created on first use."""
    account = BankAccount.objects.filter(is_gateway=True, is_active=True).first()
    return account or BankAccountFactory(gateway=True)


class BankDepositFactory(factory.django.DjangoModelFactory):
    """Pending cash deposit by default; traits `settled`, `failed` and `gateway`."""

    class Meta:
        model = BankDeposit

    deposit_number = factory.Sequence(lambda n: f"DEP-T{n:06d}")
    source = BankDeposit.Source.CASH
    branch = factory.SubFactory(BranchFactory)
    bank_account = factory.SubFactory(BankAccountFactory)
    reference_number = factory.Sequence(lambda n: f"SLIP{n:08d}")
    deposit_date = factory.LazyFunction(business_date)
    expected_amount = Decimal("5000.00")
    deposited_amount = factory.SelfAttribute("expected_amount")
    created_by = factory.SubFactory(BranchManagerFactory, branch=factory.SelfAttribute("..branch"))
    idempotency_key = factory.LazyFunction(uuid.uuid4)

    class Params:
        settled = factory.Trait(
            status=BankDeposit.Status.SETTLED,
            settled_amount=factory.SelfAttribute("deposited_amount"),
            settled_on=factory.SelfAttribute("deposit_date"),
            settled_at=factory.LazyFunction(timezone.now),
            settlement_reference=factory.Sequence(lambda n: f"STMT{n:06d}"),
        )
        failed = factory.Trait(
            status=BankDeposit.Status.FAILED,
            failed_at=factory.LazyFunction(timezone.now),
            failure_reason="Slip rejected by bank.",
        )
        gateway = factory.Trait(
            source=BankDeposit.Source.GATEWAY,
            branch=None,
            bank_account=factory.LazyFunction(gateway_bank_account),
            created_by=factory.SubFactory(FinanceUserFactory),
            reference_number=factory.Sequence(lambda n: f"UTR{n:010d}"),
        )


class CollectionFactory(factory.django.DjangoModelFactory):
    """A cash receipt in `COLLECTED` state. Use `upi=True` for a gateway payment."""

    class Meta:
        model = Collection

    receipt_number = factory.Sequence(lambda n: f"RCT-T{n:08d}")
    loan = factory.SubFactory(LoanFactory)
    customer = factory.SelfAttribute("loan.customer")
    branch = factory.SelfAttribute("loan.branch")
    agent = factory.LazyAttribute(lambda o: o.loan.customer.assigned_agent)
    amount = Decimal("1000.00")
    mode = Collection.Mode.CASH
    idempotency_key = factory.LazyFunction(uuid.uuid4)

    class Params:
        upi = factory.Trait(
            mode=Collection.Mode.UPI,
            idempotency_key=None,
            gateway_payment_id=factory.Sequence(lambda n: f"pay_test{n:010d}"),
        )


class AllocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Allocation

    collection = factory.SubFactory(CollectionFactory)
    installment = factory.LazyAttribute(
        lambda o: o.collection.loan.installments.order_by("installment_no").first()
    )
    amount = factory.SelfAttribute("collection.amount")


class DiscrepancyFactory(factory.django.DjangoModelFactory):
    """Open cash shortage on an approved-with-discrepancy submission."""

    class Meta:
        model = Discrepancy

    kind = Discrepancy.Kind.CASH_SHORTAGE
    direction = Discrepancy.Direction.SHORT
    amount = Decimal("500.00")
    submission = factory.SubFactory(CashSubmissionFactory, short=True)
    branch = factory.SelfAttribute("submission.branch")
    agent = factory.SelfAttribute("submission.agent")
    reason_code = Discrepancy.ReasonCode.COUNTING_ERROR
    notes = "Counted short at the branch."
    raised_by = factory.SelfAttribute("submission.reviewed_by")


class GatewayOrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GatewayOrder

    provider = GatewayProvider.MOCK
    provider_order_id = factory.Sequence(lambda n: f"order_mock{n:010d}")
    receipt = factory.Sequence(lambda n: f"ORD-T{n:08d}")
    loan = factory.SubFactory(LoanFactory)
    agent = factory.LazyAttribute(lambda o: o.loan.customer.assigned_agent)
    amount = Decimal("1000.00")
    idempotency_key = factory.LazyFunction(uuid.uuid4)


class WebhookEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = WebhookEvent

    provider = GatewayProvider.MOCK
    event_id = factory.Sequence(lambda n: f"evt_test{n:010d}")
    event_type = "payment.captured"
    payload = factory.LazyAttribute(lambda o: {"event": o.event_type, "id": o.event_id})


class AuditLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditLog

    actor = factory.SubFactory(AdminUserFactory)
    action = AuditAction.BRANCH_UPDATED
    entity_type = "branch"
    entity_id = factory.Sequence(str)
    after = factory.LazyFunction(dict)
