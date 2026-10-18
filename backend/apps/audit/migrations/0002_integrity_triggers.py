"""Database-level guards for reconciled records.

Services refuse these changes first with friendly errors; the triggers make the
rules hold for anything else that reaches the database (admin, shell, raw SQL).
Every violation raises `RECORD_LOCKED: <reason>`, which the API maps to HTTP 409.
"""

from django.db import migrations

FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION cashtrail_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'RECORD_LOCKED: % on % is not allowed', TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit_auditlog
    FOR EACH ROW EXECUTE FUNCTION cashtrail_block_mutation();

CREATE TRIGGER allocation_no_delete
    BEFORE DELETE ON collections_allocation
    FOR EACH ROW EXECUTE FUNCTION cashtrail_block_mutation();

CREATE TRIGGER installment_no_delete
    BEFORE DELETE ON loans_installment
    FOR EACH ROW EXECUTE FUNCTION cashtrail_block_mutation();


CREATE OR REPLACE FUNCTION allocation_guard() RETURNS trigger AS $$
BEGIN
    IF (NEW.collection_id, NEW.installment_id, NEW.amount)
       IS DISTINCT FROM (OLD.collection_id, OLD.installment_id, OLD.amount) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: allocations are immutable; void the collection instead';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER allocation_lock
    BEFORE UPDATE ON collections_allocation
    FOR EACH ROW EXECUTE FUNCTION allocation_guard();


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

CREATE TRIGGER collection_lock
    BEFORE UPDATE OR DELETE ON collections_collection
    FOR EACH ROW EXECUTE FUNCTION collection_guard();


-- deposit_id stays writable: a failed deposit releases its submissions for redeposit.
CREATE OR REPLACE FUNCTION submission_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: cash submission % cannot be deleted', OLD.submission_number;
    END IF;
    IF OLD.status <> 'SUBMITTED' AND (
        NEW.status, NEW.expected_amount, NEW.declared_amount, NEW.received_amount,
        NEW.denominations, NEW.agent_id, NEW.branch_id, NEW.reviewed_by_id, NEW.reviewed_at,
        NEW.review_remarks, NEW.rejection_reason
    ) IS DISTINCT FROM (
        OLD.status, OLD.expected_amount, OLD.declared_amount, OLD.received_amount,
        OLD.denominations, OLD.agent_id, OLD.branch_id, OLD.reviewed_by_id, OLD.reviewed_at,
        OLD.review_remarks, OLD.rejection_reason
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: cash submission % is already % and cannot be changed',
            OLD.submission_number, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER submission_lock
    BEFORE UPDATE OR DELETE ON reconciliation_cashsubmission
    FOR EACH ROW EXECUTE FUNCTION submission_guard();


CREATE OR REPLACE FUNCTION deposit_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: bank deposit % cannot be deleted', OLD.deposit_number;
    END IF;
    IF OLD.status <> 'PENDING' AND (
        NEW.status, NEW.source, NEW.branch_id, NEW.bank_account_id, NEW.reference_number,
        NEW.deposit_date, NEW.expected_amount, NEW.deposited_amount, NEW.fee_amount,
        NEW.tax_amount, NEW.settled_amount, NEW.settled_on, NEW.settlement_reference
    ) IS DISTINCT FROM (
        OLD.status, OLD.source, OLD.branch_id, OLD.bank_account_id, OLD.reference_number,
        OLD.deposit_date, OLD.expected_amount, OLD.deposited_amount, OLD.fee_amount,
        OLD.tax_amount, OLD.settled_amount, OLD.settled_on, OLD.settlement_reference
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: bank deposit % is % and cannot be changed',
            OLD.deposit_number, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER deposit_lock
    BEFORE UPDATE OR DELETE ON deposits_bankdeposit
    FOR EACH ROW EXECUTE FUNCTION deposit_guard();


CREATE OR REPLACE FUNCTION discrepancy_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: discrepancies cannot be deleted';
    END IF;
    IF OLD.status <> 'OPEN' AND (
        NEW.status, NEW.kind, NEW.direction, NEW.amount, NEW.submission_id, NEW.deposit_id,
        NEW.resolution_notes, NEW.resolved_by_id, NEW.resolved_at
    ) IS DISTINCT FROM (
        OLD.status, OLD.kind, OLD.direction, OLD.amount, OLD.submission_id, OLD.deposit_id,
        OLD.resolution_notes, OLD.resolved_by_id, OLD.resolved_at
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: discrepancy % is already %', OLD.id, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER discrepancy_lock
    BEFORE UPDATE OR DELETE ON reconciliation_discrepancy
    FOR EACH ROW EXECUTE FUNCTION discrepancy_guard();
"""

REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS discrepancy_lock ON reconciliation_discrepancy;
DROP FUNCTION IF EXISTS discrepancy_guard();
DROP TRIGGER IF EXISTS deposit_lock ON deposits_bankdeposit;
DROP FUNCTION IF EXISTS deposit_guard();
DROP TRIGGER IF EXISTS submission_lock ON reconciliation_cashsubmission;
DROP FUNCTION IF EXISTS submission_guard();
DROP TRIGGER IF EXISTS collection_lock ON collections_collection;
DROP FUNCTION IF EXISTS collection_guard();
DROP TRIGGER IF EXISTS allocation_lock ON collections_allocation;
DROP FUNCTION IF EXISTS allocation_guard();
DROP TRIGGER IF EXISTS installment_no_delete ON loans_installment;
DROP TRIGGER IF EXISTS allocation_no_delete ON collections_allocation;
DROP TRIGGER IF EXISTS audit_log_append_only ON audit_auditlog;
DROP FUNCTION IF EXISTS cashtrail_block_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("collections", "0001_initial"),
        ("deposits", "0001_initial"),
        ("loans", "0001_initial"),
        ("reconciliation", "0001_initial"),
    ]

    operations = [migrations.RunSQL(FORWARD_SQL, REVERSE_SQL)]
