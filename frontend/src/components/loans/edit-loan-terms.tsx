"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, PencilLine } from "lucide-react";
import { useState } from "react";

import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Button } from "@/components/ui/button";
import { loanQueries, useUpdateLoanTerms } from "@/features/loans/api";
import { addDays, todayIST } from "@/lib/dates";
import { normalizeMoney } from "@/lib/money";
import type { ID, Loan } from "@/types/domain";

import { LoanTermFields, SchedulePreviewView, useLoanTermsDraft, type LoanTermsValues } from "./loan-terms";

function termsOf(loan: Loan): LoanTermsValues {
  return {
    principal: loan.principal,
    rate: loan.annual_interest_rate,
    tenure: String(loan.tenure_months),
    disbursed: loan.disbursed_on,
    firstDue: loan.first_due_date,
  };
}

/** "Edit terms" for a loan with no repayment yet; renders nothing once the terms are locked. */
export function EditLoanTerms({ loanId }: { loanId: ID }) {
  const loan = useQuery(loanQueries.detail(loanId));
  const [open, setOpen] = useState(false);
  if (!loan.data || loan.data.terms_locked || loan.data.status !== "ACTIVE") return null;

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <PencilLine data-icon="inline-start" />
        Edit terms
      </Button>
      <EditLoanTermsDialog loan={loan.data} open={open} onOpenChange={setOpen} />
    </>
  );
}

function EditLoanTermsDialog({ loan, open, onOpenChange }: { loan: Loan; open: boolean; onOpenChange: (open: boolean) => void }) {
  const draft = useLoanTermsDraft(termsOf(loan), { enabled: open });
  const [wasOpen, setWasOpen] = useState(open);
  const update = useUpdateLoanTerms({ onSuccess: () => onOpenChange(false) });

  // Start from the saved terms each time the dialog opens.
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) draft.reset(termsOf(loan));
  }

  const schedule = draft.preview.data;
  const changed =
    schedule !== undefined &&
    (schedule.principal !== loan.principal ||
      normalizeMoney(schedule.annual_interest_rate) !== normalizeMoney(loan.annual_interest_rate) ||
      schedule.disbursed_on !== loan.disbursed_on ||
      schedule.first_due_date !== loan.first_due_date);
  const ready = draft.settled && draft.parsedPrincipal !== null && draft.rateValid && changed;
  // A loan disbursed more than 60 days ago keeps its own date selectable.
  const minDisbursed = [loan.disbursed_on, addDays(todayIST(), -60)].sort()[0];

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(next) => !update.isPending && onOpenChange(next)}
      title={`Edit terms · ${loan.loan_number}`}
      description="Allowed until the first repayment. The schedule is rebuilt and the agent sees the new EMI right away."
      className="sm:max-w-[860px]"
      footer={
        <Button
          disabled={!ready || update.isPending}
          onClick={() =>
            schedule &&
            update.mutate({
              id: loan.id,
              principal: schedule.principal,
              annual_interest_rate: schedule.annual_interest_rate,
              disbursed_on: schedule.disbursed_on,
              first_due_date: schedule.first_due_date,
            })
          }
        >
          {update.isPending && <Loader2 className="animate-spin" />}
          Save terms
        </Button>
      }
    >
      <div className="grid items-start gap-5 md:grid-cols-[300px_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <LoanTermFields draft={draft} editing minDisbursed={minDisbursed} />
        </div>
        <SchedulePreviewView draft={draft} compact />
      </div>
    </ResponsiveDialog>
  );
}
