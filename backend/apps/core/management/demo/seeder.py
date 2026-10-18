"""Builds the demo dataset by replaying a few months of branch operations through the services.

Every step runs at its historical moment (see `travel_to`), so timestamps, document numbers,
ageing, SLA checks and the audit trail come out as if the work had happened on those days, and
every rule the services and the database enforce holds for the demo data as well.

The day-to-day flow is: agents visit customers and collect EMIs (cash or UPI), hand their cash
to the branch in the evening, the manager counts it the next morning and banks it after lunch,
finance confirms deposits against the bank statement the following day, and gateway settlements
arrive every third day. A handful of scripted events on top of that produce every exception the
system handles: shortages, excess, rejection, voids, failed and short deposits, mismatched and
delayed settlements, cash still with agents and work waiting for review.
"""

import json
import logging
import random
import string
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import partial
from unittest import mock

from dateutil.relativedelta import relativedelta
from django.db.models import QuerySet
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import create_user
from apps.branches.models import Branch
from apps.branches.services import create_branch
from apps.collections.models import Collection
from apps.collections.services import record_collection, void_collection
from apps.core.dates import business_date, day_bounds
from apps.core.money import ZERO, money_to_paise, to_money
from apps.customers.models import Customer
from apps.customers.services import create_customer
from apps.deposits.models import BankAccount, BankDeposit
from apps.deposits.selectors import unsettled_upi_collections, unsettled_upi_total
from apps.deposits.services import (
    create_bank_account,
    create_deposit,
    fail_deposit,
    flag_delayed_settlements,
    record_gateway_settlement,
    settle_deposit,
)
from apps.loans.models import Installment, Loan
from apps.loans.schedule import generate_schedule
from apps.loans.services import create_loan
from apps.payments.models import CHECKOUT_WINDOW, GatewayOrder
from apps.payments.providers import MockProvider, get_provider
from apps.payments.services import create_order, expire_stale_orders, handle_webhook
from apps.reconciliation.models import CashSubmission, Discrepancy
from apps.reconciliation.selectors import submission_collections
from apps.reconciliation.services import (
    approve_submission,
    create_submission,
    reject_submission,
    resolve_discrepancy,
)

from . import data

CASH, UPI = Collection.Mode.CASH, Collection.Mode.UPI
RESOLVED, WRITTEN_OFF = Discrepancy.Status.RESOLVED, Discrepancy.Status.WRITTEN_OFF
Reason = Discrepancy.ReasonCode

# Repayment behaviour of a borrower, and how many of the 55 demo loans behave that way.
REGULAR, PARTIAL, LATE, DEFAULTER, FORECLOSER = "regular", "partial", "late", "defaulter", "closer"
PROFILE_MIX = {REGULAR: 26, PARTIAL: 9, LATE: 8, DEFAULTER: 7, FORECLOSER: 5}
REPEAT_BORROWERS = 10
ANNUAL_RATES = ("12.00", "13.50", "14.00", "15.00", "16.50", "18.00", "19.50", "21.00", "24.00")
TENURES = (6, 9, 12, 18, 24)

# What an agent collects on a visit; amounts are worked out from the loan on the day.
EMI, PART, TOP_UP, FORECLOSE, ANY, FIXED, MISKEYED = (
    "emi",
    "part",
    "top_up",
    "foreclose",
    "any",
    "fixed",
    "miskeyed",
)
VISIT_REMARKS = {
    PART: "Part payment; customer promised the balance next week.",
    TOP_UP: "Balance of the earlier part payment.",
    FORECLOSE: "Foreclosure: loan paid off in full.",
}

GATEWAY_FEE_RATE = Decimal("0.02")
GST_RATE = Decimal("0.18")
GATEWAY_SETTLEMENT_LAG_DAYS = 2
NOTE_MIX = (500, 200, 100, 50, 20, 10, 5, 2, 1)
TOKEN_ALPHABET = string.ascii_letters + string.digits


@dataclass(frozen=True, slots=True)
class Review:
    """How the branch handles one agent's evening hand-over when counting it next morning."""

    shortfall: Decimal = ZERO  # expected - counted; negative means excess cash
    reason_code: str = ""
    remarks: str = ""
    reject: str = ""
    hold: bool = False
    follow_up: tuple[int, str, str] | None = None  # (days later, outcome, resolution notes)


# Keyed by (agent, day offset of the hand-over); every other hand-over is approved as counted.
REVIEWS = {
    ("agent.mum2", -34): Review(
        Decimal("1000.00"),
        Reason.AGENT_SHORTAGE,
        "Agent was 1,000 short at hand-over; says one customer's cash was left at home.",
        follow_up=(3, RESOLVED, "Agent paid in the 1,000 shortfall against a branch receipt."),
    ),
    ("agent.del3", -27): Review(
        Decimal("40.00"),
        Reason.COUNTING_ERROR,
        "Two mutilated 20 notes refused at the count.",
        follow_up=(1, WRITTEN_OFF, "Below the recovery threshold; written off."),
    ),
    ("agent.blr3", -20): Review(
        Decimal("-200.00"),
        Reason.COUNTING_ERROR,
        "Recount found 200 more than the receipts; the agent's own float was mixed in.",
        follow_up=(1, RESOLVED, "Excess 200 returned to the agent against a signed slip."),
    ),
    ("agent.blr1", -13): Review(
        Decimal("1500.00"),
        Reason.AGENT_SHORTAGE,
        "Counted 48,500 against 50,000 receipted; the agent cannot account for 1,500.",
    ),
    ("agent.del1", -10): Review(
        reject="Cash and receipts do not tally; recount and resubmit with the receipt copies.",
    ),
    ("agent.mum1", -1): Review(hold=True),
    ("agent.blr2", -1): Review(hold=True),
}
# The 50,000 hand-over above is made of exactly these receipts.
FIXED_COLLECTIONS = {
    ("agent.blr1", -13): (Decimal("22500.00"), Decimal("15000.00"), Decimal("12500.00")),
}

SHORT_DEPOSIT, BANK_CHARGES, BOUNCED, UNCONFIRMED = "short", "charges", "bounced", "unconfirmed"
# Keyed by (branch, day offset of the deposit); finance settles every other deposit in full.
DEPOSIT_EVENTS = {
    ("MUM01", -22): SHORT_DEPOSIT,
    ("BLR01", -17): BANK_CHARGES,
    ("DEL01", -15): BOUNCED,
    ("BLR01", -6): UNCONFIRMED,
}
BANK_CHARGES_AMOUNT = Decimal("118.00")
COUNTERFEIT_NOTE = Decimal("500.00")
# Agent whose cash is collected the day before each scripted deposit, so there is cash to bank.
DEPOSIT_FEEDERS = {"BLR01": "agent.blr2", "MUM01": "agent.mum3", "DEL01": "agent.del2"}

# The current picture on the dashboards: cash still with an agent, a hand-over awaiting the
# count, cash counted but not yet banked, deposits awaiting the statement, unsettled UPI.
AGENTS_HOLDING_CASH = frozenset({"agent.del2", "agent.blr1"})
DEPOSITS_PAUSED_FROM = {"MUM01": -1, "BLR01": -1}
RECENT_VISITS = (
    ("agent.blr1", -2, CASH),
    ("agent.blr1", -1, CASH),
    ("agent.blr1", 0, CASH),
    ("agent.blr1", 0, CASH),
    ("agent.blr2", -1, CASH),
    ("agent.blr2", -1, CASH),
    ("agent.blr3", -2, CASH),
    ("agent.del1", -2, CASH),
    ("agent.mum2", -2, CASH),
    ("agent.mum1", -1, CASH),
    ("agent.del2", -1, CASH),
    ("agent.del2", -1, CASH),
    ("agent.blr3", -1, UPI),
    ("agent.mum3", -1, UPI),
)
MISKEYED_VISIT = ("agent.blr2", -7)
GATEWAY_MISMATCH_FROM = -10
GATEWAY_REFUND_ADJUSTMENT = Decimal("25.00")


@contextmanager
def travel_to(moment: datetime) -> Iterator[None]:
    """Pin `timezone.now()`, and with it `business_date()`, for the services called inside."""
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


def cash_count(amount: Decimal) -> dict[str, int] | None:
    """A plausible note-and-coin breakdown of a whole-rupee amount; None if it carries paise."""
    if amount != amount.to_integral_value():
        return None
    remaining, counts = int(amount), {}
    for note in NOTE_MIX:
        count, remaining = divmod(remaining, note)
        if count:
            counts[str(note)] = count
    return counts


@dataclass(slots=True)
class CustomerPlan:
    branch_code: str
    agent: str
    full_name: str
    phone: str
    address: str
    onboarded_on: date | None = None
    record: Customer | None = None


@dataclass(slots=True)
class LoanPlan:
    customer: CustomerPlan
    profile: str
    principal: Decimal
    rate: Decimal
    tenure_months: int
    first_due_date: date
    upi_share: float
    record: Loan | None = None

    @property
    def disbursed_on(self) -> date:
        return self.first_due_date - relativedelta(months=1)


@dataclass(frozen=True, slots=True)
class Visit:
    agent: str
    kind: str
    mode: str = CASH
    loan: LoanPlan | None = None
    amount: Decimal | None = None


class DemoSeeder:
    def __init__(self, *, seed: int):
        self.rng = random.Random(seed)
        self.now = timezone.now()
        self.today = business_date(self.now)
        self.agenda: dict[date, list[tuple[time, Callable[[date], None]]]] = defaultdict(list)
        self.visits: dict[date, list[Visit]] = defaultdict(list)
        self.deposit_events: dict[int, str] = {}
        self.branches: dict[str, Branch] = {}
        self.bank_accounts: dict[str, BankAccount] = {}
        self.agents: dict[str, User] = {}
        self.managers: dict[str, User] = {}
        self.admin: User | None = None
        self.finance: User | None = None
        self.gateway_mismatch_pending = True
        self.late_capture_pending = True
        self.gateway: MockProvider | None = None
        self.profiles: dict[int, str] = {}  # loan id -> repayment behaviour

    def run(self) -> None:
        """Seed everything; call inside a transaction so a failure leaves nothing behind."""
        customers, loans = self._plan_portfolio()
        start = min(customer.onboarded_on for customer in customers) - timedelta(days=7)
        self._schedule(start, time(9, 30), self._set_up_organisation)
        for customer in customers:
            self._schedule(customer.onboarded_on, time(11, 0), partial(self._onboard, customer))
        for plan in loans:
            self._schedule(plan.disbursed_on, time(12, 0), partial(self._disburse, plan))
            self._plan_repayments(plan)
        self._plan_scripted_visits()

        # UPI goes through the offline gateway so seeding never calls a real one.
        with override_settings(PAYMENT_PROVIDER="mock"):
            self.gateway = get_provider()
            day = start
            while day <= self.today:
                self._run_day(day)
                day += timedelta(days=1)
            with travel_to(self.now - timedelta(minutes=3)):
                self._leave_order_awaiting_payment()

    # Planning ---------------------------------------------------------------------------------

    def _plan_portfolio(self) -> tuple[list[CustomerPlan], list[LoanPlan]]:
        customers = []
        for branch in data.BRANCHES:
            agents = [
                staff.username
                for staff in data.STAFF
                if staff.branch_code == branch.code and staff.role == User.Role.AGENT
            ]
            for index, name in enumerate(data.CUSTOMER_NAMES[branch.code]):
                customers.append(
                    CustomerPlan(
                        branch_code=branch.code,
                        agent=agents[index % len(agents)],
                        full_name=name,
                        phone=data.mobile_number(self.rng),
                        address=data.customer_address(branch.code, self.rng),
                    )
                )
        borrowers = customers + self.rng.sample(customers, REPEAT_BORROWERS)
        profiles = [profile for profile, count in PROFILE_MIX.items() for _ in range(count)]
        self.rng.shuffle(profiles)

        loans = [
            self._loan_terms(customer, profile, repeat=index >= len(customers))
            for index, (customer, profile) in enumerate(zip(borrowers, profiles, strict=True))
        ]
        self._anchor_fixed_collections(loans)
        for plan in loans:
            onboarded = plan.disbursed_on - timedelta(days=self.rng.randint(1, 6))
            customer = plan.customer
            customer.onboarded_on = min(onboarded, customer.onboarded_on or onboarded)
        return customers, loans

    def _loan_terms(self, customer: CustomerPlan, profile: str, *, repeat: bool) -> LoanPlan:
        # Foreclosures are realistic only on small, short loans.
        closer = profile == FORECLOSER
        principal = self.rng.randrange(25_000, 60_001 if closer else 300_001, 5_000)
        tenure = self.rng.choice(TENURES[:3] if closer else TENURES)
        months_back = self.rng.randint(30, 70) if repeat else self.rng.randint(30, 120)
        return LoanPlan(
            customer=customer,
            profile=profile,
            principal=Decimal(principal),
            rate=Decimal(self.rng.choice(ANNUAL_RATES)),
            tenure_months=tenure,
            first_due_date=self.today - timedelta(days=months_back),
            upi_share=0.75 if self.rng.random() < 0.3 else 0.05,
        )

    def _anchor_fixed_collections(self, loans: list[LoanPlan]) -> None:
        """Give each agent with a fixed hand-over enough sizeable, healthy loans to carry it."""
        for (agent, _), amounts in FIXED_COLLECTIONS.items():
            own = [plan for plan in loans if plan.customer.agent == agent]
            for plan in own[: len(amounts)]:
                plan.profile = REGULAR
                plan.principal = Decimal(self.rng.randrange(150_000, 300_001, 5_000))
                plan.tenure_months = max(plan.tenure_months, 12)

    def _plan_repayments(self, plan: LoanPlan) -> None:
        rows = generate_schedule(plan.principal, plan.rate, plan.tenure_months, plan.first_due_date)
        due_dates = [row.due_date for row in rows if row.due_date <= self.today + timedelta(days=3)]
        agent = plan.customer.agent

        def visit(day: date, kind: str, mode: str | None = None) -> None:
            if plan.disbursed_on < day <= self.today:
                mode = mode or (UPI if self.rng.random() < plan.upi_share else CASH)
                self.visits[day].append(Visit(agent, kind, mode, loan=plan))

        if plan.profile == DEFAULTER:
            due_dates = due_dates[: self.rng.randint(0, 1)]
            if self.rng.random() < 0.5:
                visit(self.today - timedelta(days=self.rng.randint(3, 30)), PART)
        for due in due_dates:
            if plan.profile == LATE:
                visit(due + timedelta(days=self.rng.randint(8, 20)), EMI)
            elif plan.profile == PARTIAL:
                paid_on = due + timedelta(days=self.rng.randint(-2, 3))
                visit(paid_on, PART)
                if self.rng.random() < 0.6:
                    visit(paid_on + timedelta(days=self.rng.randint(8, 14)), TOP_UP)
            else:
                visit(due + timedelta(days=self.rng.randint(-3, 3)), EMI)
        if plan.profile == FORECLOSER:
            earliest = plan.first_due_date + timedelta(days=5)
            closing = max(earliest, self.today - timedelta(days=self.rng.randint(3, 40)))
            visit(closing, FORECLOSE, UPI if self.rng.random() < 0.6 else CASH)

    def _plan_scripted_visits(self) -> None:
        for (agent, offset), amounts in FIXED_COLLECTIONS.items():
            day = self._day(offset)
            self.visits[day] = [v for v in self.visits[day] if v.agent != agent]
            self.visits[day] += [Visit(agent, FIXED, amount=amount) for amount in amounts]
        pinned = [key for key in REVIEWS if key not in FIXED_COLLECTIONS]
        pinned += [(DEPOSIT_FEEDERS[branch], offset - 1) for branch, offset in DEPOSIT_EVENTS]
        for agent, offset in pinned:
            self.visits[self._day(offset)].append(Visit(agent, ANY))
        for agent, offset, mode in RECENT_VISITS:
            self.visits[self._day(offset)].append(Visit(agent, ANY, mode))
        agent, offset = MISKEYED_VISIT
        self.visits[self._day(offset)].append(Visit(agent, MISKEYED))

        self._schedule(self._day(-8), time(12, 10), partial(self._abandoned_order, "agent.blr3"))
        self._schedule(self._day(-5), time(16, 20), partial(self._declined_order, "agent.mum1"))

    # The day loop -----------------------------------------------------------------------------

    def _run_day(self, day: date) -> None:
        events = [
            (time(9, 0), self._flag_delayed_settlements),
            (time(10, 30), self._review_hand_overs),
            (time(12, 0), self._record_gateway_settlement),
            (time(14, 0), self._bank_branch_cash),
            (time(15, 30), self._confirm_deposits),
            (time(18, 30), self._hand_over_cash),
            *self.agenda.pop(day, []),
            *self._visit_events(day),
        ]
        for at, action in sorted(events, key=lambda event: event[0]):
            moment = timezone.make_aware(datetime.combine(day, at))
            if moment >= self.now:
                break
            with travel_to(moment):
                action(day)

    def _visit_events(self, day: date) -> list[tuple[time, Callable[[date], None]]]:
        """Each agent works through the day's visits one after another from mid-morning."""
        by_agent: dict[str, list[Visit]] = defaultdict(list)
        for visit in self.visits.pop(day, []):
            by_agent[visit.agent].append(visit)
        events = []
        for agent in self.agents:
            clock = datetime.combine(day, time(9, 45)) + timedelta(minutes=self.rng.randint(0, 40))
            for visit in by_agent.get(agent, ()):
                events.append((clock.time(), partial(self._make_visit, visit)))
                clock += timedelta(minutes=self.rng.randint(30, 70))
        return events

    def _schedule(self, day: date, at: time, action: Callable[[date], None]) -> None:
        self.agenda[day].append((at, action))

    def _day(self, offset: int) -> date:
        return self.today + timedelta(days=offset)

    def _offset(self, day: date) -> int:
        return (day - self.today).days

    # Organisation, customers and loans --------------------------------------------------------

    def _set_up_organisation(self, day: date) -> None:
        admin, *team = data.STAFF
        self.admin = self._create_staff(None, admin)
        User.objects.filter(pk=self.admin.pk).update(is_staff=True, is_superuser=True)
        self.branches = {
            branch.code: create_branch(
                self.admin,
                code=branch.code,
                name=branch.name,
                city=branch.city,
                address=branch.address,
            )
            for branch in data.BRANCHES
        }
        self.bank_accounts = {
            branch.code: create_bank_account(
                self.admin,
                bank_name=branch.bank_name,
                account_name=data.COMPANY_ACCOUNT_NAME,
                account_number_last4=branch.account_last4,
                ifsc=branch.ifsc,
            )
            for branch in data.BRANCHES
        }
        create_bank_account(self.admin, **data.GATEWAY_ACCOUNT)
        users = [self._create_staff(self.admin, staff) for staff in team]
        self.finance = next(user for user in users if user.is_finance)
        self.managers = {user.branch.code: user for user in users if user.is_branch_manager}
        self.agents = {user.username: user for user in users if user.is_agent}

    def _create_staff(self, actor, staff: data.StaffData) -> User:
        branch = self.branches[staff.branch_code] if staff.branch_code else None
        user = create_user(
            actor,
            username=staff.username,
            password=data.DEMO_PASSWORD,
            role=staff.role,
            branch=branch,
            first_name=staff.first_name,
            last_name=staff.last_name,
            email=f"{staff.username}@{data.EMAIL_DOMAIN}",
            phone=data.mobile_number(self.rng),
        )
        User.objects.filter(pk=user.pk).update(date_joined=timezone.now())
        return user

    def _onboard(self, customer: CustomerPlan, day: date) -> None:
        customer.record = create_customer(
            self.managers[customer.branch_code],
            full_name=customer.full_name,
            phone=customer.phone,
            address=customer.address,
            assigned_agent=self.agents[customer.agent],
        )

    def _disburse(self, plan: LoanPlan, day: date) -> None:
        plan.record = create_loan(
            self.managers[plan.customer.branch_code],
            customer_id=plan.customer.record.pk,
            principal=plan.principal,
            annual_interest_rate=plan.rate,
            tenure_months=plan.tenure_months,
            disbursed_on=plan.disbursed_on,
            first_due_date=plan.first_due_date,
        )
        self.profiles[plan.record.pk] = plan.profile

    # Field collections ------------------------------------------------------------------------

    def _make_visit(self, visit: Visit, day: date) -> None:
        agent = self.agents[visit.agent]
        if visit.kind == FIXED:
            loan = self._loan_for(agent, day=day, minimum=visit.amount)
            self._collect(agent, loan, visit.amount, CASH)
            return
        if visit.loan is not None:
            loan = Loan.objects.select_related("branch").get(pk=visit.loan.record.pk)
            if loan.is_closed:
                return
        else:
            loan = self._loan_for(agent, day=day, spare=visit.kind == MISKEYED)
        amount = self._amount_for(loan, visit.kind, day)
        if amount <= ZERO:
            return
        if visit.kind == FORECLOSE and visit.mode == CASH and self.late_capture_pending:
            self.late_capture_pending = False
            self._foreclose_after_abandoned_upi(agent, loan, amount)
            return
        if visit.kind != MISKEYED:
            self._collect(agent, loan, amount, visit.mode, VISIT_REMARKS.get(visit.kind, ""))
            return

        moment = timezone.now()
        miskeyed = min(amount * 10, loan.outstanding)
        wrong = self._collect(agent, loan, miskeyed, CASH)
        with travel_to(moment + timedelta(minutes=3)):
            void_collection(
                actor=agent,
                collection=wrong,
                reason=f"Keyed {miskeyed} instead of {amount}; receipt reissued.",
            )
        with travel_to(moment + timedelta(minutes=5)):
            self._collect(agent, loan, amount, CASH)

    def _loan_for(
        self,
        agent: User,
        *,
        day: date,
        minimum: Decimal = ZERO,
        spare: bool = False,
    ) -> Loan:
        """One of the agent's open, well-behaved loans, preferably with an EMI due around `day`.

        Scripted visits stay away from defaulting and late borrowers so their arrears remain.
        """
        loans = [
            loan
            for loan in Loan.objects.filter(
                customer__assigned_agent=agent, status=Loan.Status.ACTIVE
            )
            .select_related("branch")
            .order_by("pk")
            if loan.outstanding >= minimum
        ]
        loans = [loan for loan in loans if self.profiles[loan.pk] not in (DEFAULTER, LATE)] or loans
        if spare:
            loans = [loan for loan in loans if loan.outstanding >= 10 * loan.emi_amount] or loans
        with_dues = [loan for loan in loans if self._dues(loan, day + timedelta(days=5))]
        return self.rng.choice(with_dues or loans)

    def _amount_for(self, loan: Loan, kind: str, day: date) -> Decimal:
        if kind == FORECLOSE:
            return loan.outstanding
        if kind == TOP_UP:
            return self._dues(loan, day)
        dues = self._dues(loan, day + timedelta(days=5))
        if kind == PART:
            share = self.rng.randint(40, 70)
            return Decimal(int(dues * share / 100) // 100 * 100)
        if kind in (ANY, MISKEYED) and not dues:
            upcoming = self._unpaid(loan).first()
            return upcoming.outstanding if upcoming else ZERO
        return dues

    def _dues(self, loan: Loan, until: date) -> Decimal:
        return sum((i.outstanding for i in self._unpaid(loan).filter(due_date__lte=until)), ZERO)

    @staticmethod
    def _unpaid(loan: Loan) -> QuerySet[Installment]:
        return loan.installments.exclude(status=Installment.Status.PAID).order_by("installment_no")

    def _collect(
        self, agent: User, loan: Loan, amount: Decimal, mode: str, remarks: str = ""
    ) -> Collection:
        if mode == UPI:
            return self._capture_upi_payment(agent, loan, amount)
        # Cash is counted in notes and coins; only UPI payments may carry paise.
        if amount != amount.to_integral_value():
            raise ValueError(f"Cash collection of {amount} is not in whole rupees.")
        collection, _ = record_collection(
            actor=agent,
            loan=loan,
            amount=amount,
            mode=CASH,
            idempotency_key=self._uuid(),
            remarks=remarks,
        )
        return collection

    # UPI through the gateway ------------------------------------------------------------------

    def _capture_upi_payment(self, agent: User, loan: Loan, amount: Decimal) -> Collection:
        """The agent raises a payment link, the customer pays, the capture webhook records it."""
        paid_at = timezone.now()
        with travel_to(paid_at - timedelta(minutes=self.rng.randint(2, 6))):
            order = self._raise_order(agent, loan, amount)
        self._deliver_webhook(order, "payment.captured", paid_at)
        order.refresh_from_db()
        return order.collection

    def _raise_order(self, agent: User, loan: Loan, amount: Decimal) -> GatewayOrder:
        order, _ = create_order(agent, loan=loan, amount=amount, idempotency_key=self._uuid())
        return order

    def _abandoned_order(self, agent_name: str, day: date) -> None:
        agent = self.agents[agent_name]
        loan = self._loan_for(agent, day=day)
        self._raise_order(agent, loan, min(loan.emi_amount, loan.outstanding))
        # The expiry job's next run, once the checkout window has passed.
        with travel_to(timezone.now() + CHECKOUT_WINDOW + timedelta(minutes=5)):
            expire_stale_orders()

    def _foreclose_after_abandoned_upi(self, agent: User, loan: Loan, amount: Decimal) -> None:
        """The customer abandons a UPI link and pays the balance in cash instead; the gateway
        captures the UPI payment late anyway, which leaves that order due for a refund."""
        moment = timezone.now()
        order = self._raise_order(agent, loan, amount)
        with travel_to(moment + CHECKOUT_WINDOW + timedelta(minutes=2)):
            expire_stale_orders()
            self._collect(agent, loan, amount, CASH, VISIT_REMARKS[FORECLOSE])
        captured_at = moment + CHECKOUT_WINDOW + timedelta(minutes=10)
        with travel_to(captured_at):
            self._deliver_webhook(order, "payment.captured", captured_at)

    def _declined_order(self, agent_name: str, day: date) -> None:
        agent = self.agents[agent_name]
        loan = self._loan_for(agent, day=day)
        order = self._raise_order(agent, loan, min(loan.emi_amount, loan.outstanding))
        failed_at = timezone.now() + timedelta(minutes=2)
        with travel_to(failed_at):
            self._deliver_webhook(
                order, "payment.failed", failed_at, error="Payment declined by the payer's bank."
            )

    def _leave_order_awaiting_payment(self) -> None:
        agent = self.agents["agent.del3"]
        loan = self._loan_for(agent, day=self.today)
        self._raise_order(agent, loan, min(loan.emi_amount, loan.outstanding))

    def _deliver_webhook(
        self, order: GatewayOrder, event_type: str, at: datetime, *, error: str = ""
    ) -> None:
        """Send the gateway's signed webhook for `order` through the production handler."""
        payment = {
            "id": f"pay_{self._token(14)}",
            "entity": "payment",
            "amount": money_to_paise(order.amount),
            "currency": "INR",
            "status": "failed" if error else "captured",
            "order_id": order.provider_order_id,
            "method": "upi",
            "error_description": error or None,
            "created_at": int(at.timestamp()),
        }
        body = json.dumps(
            {"entity": "event", "event": event_type, "payload": {"payment": {"entity": payment}}},
            separators=(",", ":"),
        ).encode()
        event, _ = handle_webhook(
            raw_body=body,
            signature=self.gateway.sign_webhook(body),
            event_id=f"evt_{self._token(14)}",
        )
        if event.processed_at is None:
            raise RuntimeError(f"Demo webhook for {order.receipt} was not applied: {event.error}")

    # Branch hand-over and review --------------------------------------------------------------

    def _hand_over_cash(self, day: date) -> None:
        for name, agent in self.agents.items():
            if name in AGENTS_HOLDING_CASH and day >= self._day(-1):
                continue
            held = list(
                Collection.objects.filter(
                    agent=agent, mode=CASH, status=Collection.Status.COLLECTED
                ).order_by("pk")
            )
            awaiting = CashSubmission.objects.filter(
                agent=agent, status=CashSubmission.Status.SUBMITTED
            )
            if not held or awaiting.exists():
                continue
            expected = sum((collection.amount for collection in held), ZERO)
            review = REVIEWS.get((name, self._offset(day)))
            # The hand-over the branch will reject is the one where the agent's count is off.
            declared = (
                to_money(int(expected * Decimal("0.9"))) if review and review.reject else expected
            )
            create_submission(
                agent,
                collection_ids=[collection.pk for collection in held],
                declared_amount=declared,
                idempotency_key=self._uuid(),
                denominations=cash_count(declared),
            )

    def _review_hand_overs(self, day: date) -> None:
        pending = (
            CashSubmission.objects.filter(
                status=CashSubmission.Status.SUBMITTED, submitted_at__lt=day_bounds(day)[0]
            )
            .select_related("agent", "branch")
            .order_by("pk")
        )
        for submission in pending:
            key = (submission.agent.username, self._offset(business_date(submission.submitted_at)))
            review = REVIEWS.get(key, Review())
            manager = self.managers[submission.branch.code]
            if review.hold:
                continue
            if review.reject:
                self._reject_and_resubmit(manager, submission, review.reject)
                continue
            received = submission.expected_amount - review.shortfall
            approve_submission(
                manager,
                submission,
                received_amount=received,
                denominations=cash_count(received),
                reason_code=review.reason_code,
                remarks=review.remarks,
            )
            if review.follow_up:
                days_later, outcome, notes = review.follow_up
                discrepancy = Discrepancy.objects.get(submission=submission)
                self._schedule(
                    day + timedelta(days=days_later),
                    time(11, 0),
                    partial(self._resolve, manager, discrepancy, outcome, notes),
                )

    def _reject_and_resubmit(self, manager: User, submission: CashSubmission, reason: str) -> None:
        moment = timezone.now()
        rejected = reject_submission(manager, submission, reason=reason)
        receipts = list(submission_collections(rejected))
        expected = sum((collection.amount for collection in receipts), ZERO)
        with travel_to(moment + timedelta(minutes=75)):
            resubmitted, _ = create_submission(
                submission.agent,
                collection_ids=[collection.pk for collection in receipts],
                declared_amount=expected,
                idempotency_key=self._uuid(),
                denominations=cash_count(expected),
            )
        with travel_to(moment + timedelta(minutes=120)):
            approve_submission(
                manager,
                resubmitted,
                received_amount=expected,
                denominations=cash_count(expected),
            )

    def _resolve(
        self, actor: User, discrepancy: Discrepancy, outcome: str, notes: str, day: date
    ) -> None:
        resolve_discrepancy(actor, discrepancy, outcome=outcome, resolution_notes=notes)

    # Bank deposits and settlement -------------------------------------------------------------

    def _bank_branch_cash(self, day: date) -> None:
        for code, manager in self.managers.items():
            paused_from = DEPOSITS_PAUSED_FROM.get(code)
            if paused_from is not None and day >= self._day(paused_from):
                continue
            submissions = list(
                CashSubmission.objects.filter(
                    branch=manager.branch,
                    status__in=CashSubmission.APPROVED_STATUSES,
                    deposit__isnull=True,
                ).order_by("pk")
            )
            if not submissions:
                continue
            expected = sum((s.received_amount for s in submissions), ZERO)
            event = DEPOSIT_EVENTS.get((code, self._offset(day)))
            short = event == SHORT_DEPOSIT and expected > COUNTERFEIT_NOTE
            account = self.bank_accounts[code]
            deposit, _ = create_deposit(
                manager,
                submission_ids=[s.pk for s in submissions],
                bank_account_id=account.pk,
                deposited_amount=expected - COUNTERFEIT_NOTE if short else expected,
                deposit_date=day,
                reference_number=self._reference(account.ifsc[:4], day, digits=6),
                remarks=(
                    "Teller impounded one 500 note as counterfeit; bank acknowledgement filed."
                    if short
                    else ""
                ),
                idempotency_key=self._uuid(),
            )
            if event:
                self.deposit_events[deposit.pk] = event

    def _confirm_deposits(self, day: date) -> None:
        """Finance matches yesterday's deposits to the statement; the latest stay pending."""
        cutoff = min(day - timedelta(days=1), self._day(-2))
        deposits = BankDeposit.objects.filter(
            source=BankDeposit.Source.CASH,
            status=BankDeposit.Status.PENDING,
            deposit_date__lte=cutoff,
        ).order_by("pk")
        for deposit in deposits:
            event = self.deposit_events.get(deposit.pk)
            if event == UNCONFIRMED:
                continue
            if event == BOUNCED:
                fail_deposit(
                    self.finance,
                    deposit,
                    reason="Bank returned the deposit: the slip carried a wrong account number.",
                )
                continue
            charges = BANK_CHARGES_AMOUNT if event == BANK_CHARGES else ZERO
            settle_deposit(
                self.finance,
                deposit,
                settled_amount=deposit.deposited_amount - charges,
                settled_on=day,
                settlement_reference=f"STMT-{day:%Y%m%d}-{self.rng.randint(1000, 9999)}",
                remarks="Bank debited a 100 cash-handling charge plus 18 GST." if charges else "",
                reason_code=Reason.BANK_CHARGES if charges else Reason.BANK_ERROR,
            )
            if charges:
                discrepancy = deposit.discrepancies.get(kind=Discrepancy.Kind.SETTLEMENT_MISMATCH)
                notes = "Charges match the bank's tariff; booked to bank charges."
                self._schedule(
                    day + timedelta(days=2),
                    time(11, 0),
                    partial(self._resolve, self.finance, discrepancy, RESOLVED, notes),
                )

    def _record_gateway_settlement(self, day: date) -> None:
        """Gateway payouts arrive every third day, net of fees, for payments up to T-2."""
        if day.toordinal() % 3:
            return
        up_to = day - timedelta(days=GATEWAY_SETTLEMENT_LAG_DAYS)
        pending = unsettled_upi_total(unsettled_upi_collections(up_to))
        if not pending.count:
            return
        gross, remarks = pending.total_amount, ""
        if self.gateway_mismatch_pending and day >= self._day(GATEWAY_MISMATCH_FROM):
            self.gateway_mismatch_pending = False
            gross -= GATEWAY_REFUND_ADJUSTMENT
            remarks = "Payout is 25.00 short: a refund adjustment we cannot match to a payment."
        fee = to_money(gross * GATEWAY_FEE_RATE)
        tax = to_money(fee * GST_RATE)
        record_gateway_settlement(
            self.finance,
            up_to_date=up_to,
            gross_amount=gross,
            fee_amount=fee,
            tax_amount=tax,
            net_amount=gross - fee - tax,
            utr=self._reference("KKBKR", day, digits=8),
            settled_on=day,
            remarks=remarks,
            idempotency_key=self._uuid(),
        )

    def _flag_delayed_settlements(self, day: date) -> None:
        # The job logs a warning per delayed deposit; for replayed days that is only noise.
        logging.disable(logging.WARNING)
        try:
            flag_delayed_settlements(today=day)
        finally:
            logging.disable(logging.NOTSET)

    # Helpers ----------------------------------------------------------------------------------

    def _uuid(self) -> uuid.UUID:
        return uuid.UUID(int=self.rng.getrandbits(128), version=4)

    def _reference(self, prefix: str, day: date, *, digits: int) -> str:
        return f"{prefix}{day:%y%m%d}{self.rng.randrange(10**digits):0{digits}d}"

    def _token(self, length: int) -> str:
        return "".join(self.rng.choices(TOKEN_ALPHABET, k=length))


def is_seeded() -> bool:
    usernames = [staff.username for staff in data.STAFF]
    codes = [branch.code for branch in data.BRANCHES]
    return (
        User.objects.filter(username__in=usernames).exists()
        or Branch.objects.filter(code__in=codes).exists()
    )
