"""Swagger sections: one tag per domain, with the first URL segments it serves.

Plain data so settings can import it before Django is set up.
"""

DOMAINS = {
    "Accounts": ("Sign-in, tokens and staff users.", ("auth", "users")),
    "Branches": ("Branches of the company.", ("branches",)),
    "Customers": ("Borrowers, their dues and agent assignment.", ("customers", "agent")),
    "Loans": ("Loans, EMI schedules and repayment history.", ("loans",)),
    "Collections": ("Repayments collected by agents, with receipts.", ("collections",)),
    "Reconciliation": (
        "Cash hand-over to the branch, verification and discrepancies.",
        ("submissions", "discrepancies", "reconciliation"),
    ),
    "Deposits": (
        "Bank accounts, bank deposits, settlement and gateway settlements.",
        ("bank-accounts", "deposits", "gateway-settlements"),
    ),
    "Payments": ("UPI repayments through the payment gateway.", ("payments",)),
    "Dashboard": ("KPIs, breakdowns and CSV reports.", ("dashboard", "reports")),
    "Audit": ("The append-only audit trail.", ("audit-logs",)),
    "Health": ("Liveness and database check.", ("health",)),
}
TAGS = [{"name": name, "description": text} for name, (text, _) in DOMAINS.items()]
TAG_BY_SEGMENT = {segment: name for name, (_, segments) in DOMAINS.items() for segment in segments}
