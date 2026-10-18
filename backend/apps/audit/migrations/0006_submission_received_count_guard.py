"""A reviewed submission keeps the branch's itemised count too, not only the agent's."""

from django.db import migrations

SUBMISSION_GUARD = r"""
CREATE OR REPLACE FUNCTION submission_guard() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'RECORD_LOCKED: cash submission % cannot be deleted', OLD.submission_number;
    END IF;
    IF OLD.status <> 'SUBMITTED' AND (
        NEW.status, NEW.expected_amount, NEW.declared_amount, NEW.received_amount,
        NEW.denominations, NEW.received_denominations, NEW.agent_id, NEW.branch_id,
        NEW.reviewed_by_id, NEW.reviewed_at, NEW.review_remarks, NEW.rejection_reason
    ) IS DISTINCT FROM (
        OLD.status, OLD.expected_amount, OLD.declared_amount, OLD.received_amount,
        OLD.denominations, OLD.received_denominations, OLD.agent_id, OLD.branch_id,
        OLD.reviewed_by_id, OLD.reviewed_at, OLD.review_remarks, OLD.rejection_reason
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


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0005_collection_lifecycle_guard"),
        ("reconciliation", "0003_received_denominations"),
    ]

    operations = [migrations.RunSQL(SUBMISSION_GUARD, PREVIOUS_SUBMISSION_GUARD)]
