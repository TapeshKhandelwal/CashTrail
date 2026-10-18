"""Holds receipts to their lifecycle at the database level.

- Status moves follow the same map as `Collection.CASH_TRANSITIONS` / `UPI_TRANSITIONS`; a
  receipt the branch has received can no longer be walked back to COLLECTED.
- The two backward moves need their paperwork: a receipt returns to the agent only from a
  rejected submission, and to the branch only from a failed deposit.
- Moving forward needs it too: received from an approved submission, settled from a
  settled deposit.
- Submission and deposit links change only with the move that sets or clears them.
- A receipt that was ever handed over keeps its amount and identity, even after rejection.
- The balance a receipt was issued with never changes once recorded.
"""

from django.db import migrations

COLLECTION_GUARD = r"""
CREATE OR REPLACE FUNCTION collection_guard() RETURNS trigger AS $$
DECLARE
    move text := OLD.status || '>' || NEW.status;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % cannot be deleted; void it instead',
            OLD.receipt_number;
    END IF;
    IF (
        NEW.amount, NEW.loan_id, NEW.customer_id, NEW.branch_id, NEW.agent_id,
        NEW.receipt_number, NEW.mode, NEW.collected_at
    ) IS DISTINCT FROM (
        OLD.amount, OLD.loan_id, OLD.customer_id, OLD.branch_id, OLD.agent_id,
        OLD.receipt_number, OLD.mode, OLD.collected_at
    ) AND (
        OLD.status <> 'COLLECTED'
        OR EXISTS (SELECT 1 FROM reconciliation_submissionitem WHERE collection_id = OLD.id)
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % is % and its financial fields are immutable',
            OLD.receipt_number, OLD.status;
    END IF;
    IF OLD.balance_after IS NOT NULL AND NEW.balance_after IS DISTINCT FROM OLD.balance_after THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % keeps the balance it was issued with',
            OLD.receipt_number;
    END IF;
    IF OLD.status IN ('SETTLED', 'VOIDED') AND (
        NEW.status, NEW.submission_id, NEW.deposit_id, NEW.settled_at,
        NEW.voided_at, NEW.void_reason, NEW.voided_by_id
    ) IS DISTINCT FROM (
        OLD.status, OLD.submission_id, OLD.deposit_id, OLD.settled_at,
        OLD.voided_at, OLD.void_reason, OLD.voided_by_id
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % is % and can no longer change',
            OLD.receipt_number, OLD.status;
    END IF;

    IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
        (OLD.mode = 'CASH' AND move IN (
            'COLLECTED>SUBMITTED', 'COLLECTED>VOIDED',
            'SUBMITTED>COLLECTED', 'SUBMITTED>BRANCH_RECEIVED',
            'BRANCH_RECEIVED>DEPOSITED',
            'DEPOSITED>BRANCH_RECEIVED', 'DEPOSITED>SETTLED'
        ))
        OR (OLD.mode = 'UPI' AND move = 'COLLECTED>SETTLED')
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % cannot move from % to %',
            OLD.receipt_number, OLD.status, NEW.status;
    END IF;

    IF OLD.status <> 'COLLECTED'
       AND NEW.submission_id IS DISTINCT FROM OLD.submission_id
       AND NOT (move = 'SUBMITTED>COLLECTED' AND NEW.submission_id IS NULL) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % cannot change its cash submission',
            OLD.receipt_number;
    END IF;
    IF OLD.status <> 'COLLECTED'
       AND NEW.deposit_id IS DISTINCT FROM OLD.deposit_id
       AND NOT (move = 'BRANCH_RECEIVED>DEPOSITED'
                OR (move = 'DEPOSITED>BRANCH_RECEIVED' AND NEW.deposit_id IS NULL)) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % cannot change its bank deposit',
            OLD.receipt_number;
    END IF;

    IF move = 'SUBMITTED>COLLECTED' AND NOT EXISTS (
        SELECT 1 FROM reconciliation_cashsubmission s
        WHERE s.id = OLD.submission_id AND s.status = 'REJECTED'
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % goes back to the agent only from a rejected submission',
            OLD.receipt_number;
    END IF;
    IF move = 'SUBMITTED>BRANCH_RECEIVED' AND NOT EXISTS (
        SELECT 1 FROM reconciliation_cashsubmission s
        WHERE s.id = NEW.submission_id
          AND s.status IN ('APPROVED', 'APPROVED_WITH_DISCREPANCY')
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % is received only through an approved submission',
            OLD.receipt_number;
    END IF;
    IF move = 'DEPOSITED>BRANCH_RECEIVED' AND NOT EXISTS (
        SELECT 1 FROM deposits_bankdeposit d WHERE d.id = OLD.deposit_id AND d.status = 'FAILED'
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % goes back to the branch only from a failed deposit',
            OLD.receipt_number;
    END IF;
    IF NEW.status = 'SETTLED' AND OLD.status <> 'SETTLED' AND NOT EXISTS (
        SELECT 1 FROM deposits_bankdeposit d
        WHERE d.id = NEW.deposit_id AND d.status IN ('SETTLED', 'SETTLED_WITH_MISMATCH')
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % settles only with a settled deposit',
            OLD.receipt_number;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

PREVIOUS_COLLECTION_GUARD = r"""
CREATE OR REPLACE FUNCTION collection_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % cannot be deleted; void it instead',
            OLD.receipt_number;
    END IF;
    IF OLD.status <> 'COLLECTED' AND (
        NEW.amount, NEW.loan_id, NEW.customer_id, NEW.branch_id, NEW.agent_id,
        NEW.receipt_number, NEW.mode, NEW.collected_at
    ) IS DISTINCT FROM (
        OLD.amount, OLD.loan_id, OLD.customer_id, OLD.branch_id, OLD.agent_id,
        OLD.receipt_number, OLD.mode, OLD.collected_at
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % is % and its financial fields are immutable',
            OLD.receipt_number, OLD.status;
    END IF;
    IF OLD.status IN ('SETTLED', 'VOIDED') AND (NEW.status, NEW.submission_id, NEW.deposit_id)
       IS DISTINCT FROM (OLD.status, OLD.submission_id, OLD.deposit_id) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: collection % is % and can no longer change',
            OLD.receipt_number, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0004_tighten_integrity_guards"),
        ("collections", "0003_balance_after"),
        ("deposits", "0002_drop_redundant_fk_index"),
    ]

    operations = [migrations.RunSQL(COLLECTION_GUARD, PREVIOUS_COLLECTION_GUARD)]
