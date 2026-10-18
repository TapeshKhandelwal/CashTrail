"""Closes gaps in the reconciled-record guards.

- A submission's deposit link can only change while that deposit is unsettled (a failed
  deposit still releases its submissions for redeposit).
- A closed discrepancy keeps who was accountable for it and why.
- Submission items are append-only.
"""

from django.db import migrations

SUBMISSION_GUARD = r"""
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
    IF NEW.deposit_id IS DISTINCT FROM OLD.deposit_id AND EXISTS (
        SELECT 1 FROM deposits_bankdeposit d
        WHERE d.id = OLD.deposit_id AND d.status IN ('SETTLED', 'SETTLED_WITH_MISMATCH')
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: cash submission % belongs to a settled deposit',
            OLD.submission_number;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

DISCREPANCY_GUARD = r"""
CREATE OR REPLACE FUNCTION discrepancy_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: discrepancies cannot be deleted';
    END IF;
    IF OLD.status <> 'OPEN' AND (
        NEW.status, NEW.kind, NEW.direction, NEW.amount, NEW.submission_id, NEW.deposit_id,
        NEW.agent_id, NEW.branch_id, NEW.reason_code, NEW.notes, NEW.raised_by_id,
        NEW.resolution_notes, NEW.resolved_by_id, NEW.resolved_at
    ) IS DISTINCT FROM (
        OLD.status, OLD.kind, OLD.direction, OLD.amount, OLD.submission_id, OLD.deposit_id,
        OLD.agent_id, OLD.branch_id, OLD.reason_code, OLD.notes, OLD.raised_by_id,
        OLD.resolution_notes, OLD.resolved_by_id, OLD.resolved_at
    ) THEN
        RAISE EXCEPTION 'RECORD_LOCKED: discrepancy % is already %', OLD.id, OLD.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

SUBMISSION_ITEM_LOCK = r"""
CREATE TRIGGER submission_item_append_only
    BEFORE UPDATE OR DELETE ON reconciliation_submissionitem
    FOR EACH ROW EXECUTE FUNCTION cashtrail_block_mutation();
"""

PREVIOUS_SUBMISSION_GUARD = r"""
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
"""

PREVIOUS_DISCREPANCY_GUARD = r"""
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
"""


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_drop_redundant_fk_indexes"),
        ("reconciliation", "0002_submission_items"),
    ]

    operations = [
        migrations.RunSQL(SUBMISSION_GUARD, PREVIOUS_SUBMISSION_GUARD),
        migrations.RunSQL(DISCREPANCY_GUARD, PREVIOUS_DISCREPANCY_GUARD),
        migrations.RunSQL(
            SUBMISSION_ITEM_LOCK,
            "DROP TRIGGER submission_item_append_only ON reconciliation_submissionitem;",
        ),
    ]
