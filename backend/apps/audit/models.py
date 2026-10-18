from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    BRANCH_CREATED = "BRANCH_CREATED", "Branch created"
    BRANCH_UPDATED = "BRANCH_UPDATED", "Branch updated"
    USER_CREATED = "USER_CREATED", "User created"
    USER_UPDATED = "USER_UPDATED", "User updated"
    BANK_ACCOUNT_CREATED = "BANK_ACCOUNT_CREATED", "Bank account created"
    BANK_ACCOUNT_UPDATED = "BANK_ACCOUNT_UPDATED", "Bank account updated"
    CUSTOMER_CREATED = "CUSTOMER_CREATED", "Customer created"
    CUSTOMER_UPDATED = "CUSTOMER_UPDATED", "Customer updated"
    CUSTOMER_ASSIGNED = "CUSTOMER_ASSIGNED", "Customer assigned to agent"
    LOAN_CREATED = "LOAN_CREATED", "Loan created"
    LOAN_UPDATED = "LOAN_UPDATED", "Loan updated"
    LOAN_CLOSED = "LOAN_CLOSED", "Loan closed"
    LOAN_REOPENED = "LOAN_REOPENED", "Loan reopened"
    COLLECTION_RECORDED = "COLLECTION_RECORDED", "Repayment recorded"
    COLLECTION_VOIDED = "COLLECTION_VOIDED", "Repayment voided"
    SUBMISSION_CREATED = "SUBMISSION_CREATED", "Cash submitted to branch"
    SUBMISSION_APPROVED = "SUBMISSION_APPROVED", "Cash submission approved"
    SUBMISSION_REJECTED = "SUBMISSION_REJECTED", "Cash submission rejected"
    DISCREPANCY_RAISED = "DISCREPANCY_RAISED", "Discrepancy raised"
    DISCREPANCY_RESOLVED = "DISCREPANCY_RESOLVED", "Discrepancy resolved"
    DISCREPANCY_WRITTEN_OFF = "DISCREPANCY_WRITTEN_OFF", "Discrepancy written off"
    DEPOSIT_CREATED = "DEPOSIT_CREATED", "Bank deposit created"
    DEPOSIT_SETTLED = "DEPOSIT_SETTLED", "Bank deposit settled"
    DEPOSIT_FAILED = "DEPOSIT_FAILED", "Bank deposit failed"
    DEPOSIT_SETTLEMENT_DELAYED = "DEPOSIT_SETTLEMENT_DELAYED", "Settlement delayed beyond SLA"
    GATEWAY_ORDER_CREATED = "GATEWAY_ORDER_CREATED", "UPI order created"
    GATEWAY_PAYMENT_CAPTURED = "GATEWAY_PAYMENT_CAPTURED", "UPI payment captured"
    GATEWAY_PAYMENT_FAILED = "GATEWAY_PAYMENT_FAILED", "UPI payment failed"
    GATEWAY_PAYMENT_REFUND_DUE = "GATEWAY_PAYMENT_REFUND_DUE", "UPI payment awaiting refund"
    GATEWAY_ORDER_EXPIRED = "GATEWAY_ORDER_EXPIRED", "UPI order expired"
    GATEWAY_SETTLEMENT_RECORDED = "GATEWAY_SETTLEMENT_RECORDED", "Gateway settlement recorded"


class AuditLog(models.Model):
    """Append-only trail of every financial change (a trigger blocks UPDATE and DELETE)."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=False,
        help_text="Empty for system actions such as gateway webhooks.",
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=64)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_index=False,
        help_text="Branch of the affected record, for scoping managers' view of the trail.",
    )
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
            models.Index(fields=["created_at"], name="audit_created_idx"),
            models.Index(fields=["actor", "created_at"], name="audit_actor_idx"),
            models.Index(fields=["branch", "created_at"], name="audit_branch_idx"),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id}"
