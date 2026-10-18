"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { ErrorState } from "@/components/feedback/error-state";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { MoneyInput } from "@/components/money/money-input";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { loanQueries } from "@/features/loans/api";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { addDays, formatDate, formatDayMonth, todayIST } from "@/lib/dates";
import { parseMoneyInput } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ISODate, LoanTermsInput } from "@/types/domain";

const TENURES = [6, 9, 12, 18, 24, 36];
export const RATE = /^\d{1,2}(\.\d{1,2})?$/;

export interface LoanTermsValues {
  principal: string;
  rate: string;
  tenure: string;
  disbursed: ISODate;
  /** Empty means one month after disbursal. */
  firstDue: ISODate | "";
}

export function newLoanTerms(): LoanTermsValues {
  return { principal: "100000", rate: "18", tenure: "12", disbursed: todayIST(), firstDue: "" };
}

/**
 * Draft loan terms with a debounced, server-computed schedule preview. `settled` is true once
 * the preview matches what is on screen, so a save never sends terms the person hasn't seen.
 */
export function useLoanTermsDraft(initial: LoanTermsValues, { enabled = true }: { enabled?: boolean } = {}) {
  const [values, setValues] = useState(initial);
  const parsedPrincipal = parseMoneyInput(values.principal);

  const current = useMemo<LoanTermsInput>(
    () => ({
      principal: parsedPrincipal ?? "",
      annual_interest_rate: values.rate,
      tenure_months: Number(values.tenure),
      disbursed_on: values.disbursed,
      ...(values.firstDue ? { first_due_date: values.firstDue } : {}),
    }),
    [parsedPrincipal, values.rate, values.tenure, values.disbursed, values.firstDue],
  );
  const terms = useDebouncedValue(current, 300);
  const termsValid = Boolean(terms.principal) && RATE.test(terms.annual_interest_rate) && terms.tenure_months > 0;
  const preview = useQuery({ ...loanQueries.schedulePreview(terms), enabled: enabled && termsValid });
  const settled = terms === current && preview.isSuccess && !preview.isPlaceholderData;

  return {
    values,
    set: (changes: Partial<LoanTermsValues>) => setValues((previous) => ({ ...previous, ...changes })),
    reset: setValues,
    parsedPrincipal,
    rateValid: RATE.test(values.rate),
    preview,
    settled,
  };
}

export type LoanTermsDraft = ReturnType<typeof useLoanTermsDraft>;

interface LoanTermFieldsProps {
  draft: LoanTermsDraft;
  /** Editing an issued loan: the tenure is fixed and the first EMI date can move. */
  editing?: boolean;
  minDisbursed?: ISODate;
}

/** Principal, rate, tenure and dates, shared by the new-loan form and the edit-terms dialog. */
export function LoanTermFields({ draft, editing = false, minDisbursed = addDays(todayIST(), -60) }: LoanTermFieldsProps) {
  const { values, set, parsedPrincipal, rateValid, preview, settled } = draft;
  const tenures = TENURES.includes(Number(values.tenure)) ? TENURES : [...TENURES, Number(values.tenure)].sort((a, b) => a - b);
  const firstDue = values.firstDue || (settled ? preview.data?.first_due_date : "") || "";

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="principal">Principal</Label>
        <MoneyInput id="principal" size="lg" value={values.principal} onValueChange={(principal) => set({ principal })} invalid={parsedPrincipal === null} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rate">Interest % a year</Label>
          <Input id="rate" inputMode="decimal" value={values.rate} onChange={(event) => set({ rate: event.target.value })} aria-invalid={!rateValid || undefined} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="tenure">Tenure</Label>
          <Select value={values.tenure} onValueChange={(tenure) => set({ tenure })} disabled={editing}>
            <SelectTrigger id="tenure" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {tenures.map((months) => (
                <SelectItem key={months} value={String(months)}>
                  {months} months
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      {editing && <p className="-mt-2 text-[12.5px] text-dim">The tenure is fixed once the schedule is issued.</p>}
      <div className={cn("grid gap-3", editing && "grid-cols-2")}>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="disbursed">Disbursed on</Label>
          <Input
            id="disbursed"
            type="date"
            value={values.disbursed}
            max={todayIST()}
            min={minDisbursed}
            // A new disbursal date moves the first EMI back to one month after it.
            onChange={(event) => set({ disbursed: event.target.value, firstDue: "" })}
          />
        </div>
        {editing && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="first-due">First EMI on</Label>
            <Input
              id="first-due"
              type="date"
              value={firstDue}
              min={addDays(values.disbursed, 1)}
              onChange={(event) => set({ firstDue: event.target.value })}
            />
          </div>
        )}
      </div>
    </>
  );
}

/** EMI, totals and the full schedule for the draft terms. `compact` fits inside a dialog. */
export function SchedulePreviewView({ draft, compact = false }: { draft: LoanTermsDraft; compact?: boolean }) {
  const { preview } = draft;
  if (preview.isError) {
    return <ErrorState error={preview.error} onRetry={() => void preview.refetch()} bordered compact title="These terms don't work." />;
  }
  const kpis = (
    <div className={cn("grid-ruled grid-cols-2", !compact && "@2xl:grid-cols-4")}>
      {[
        ["EMI", preview.data?.emi_amount],
        ["Total interest", preview.data?.total_interest],
        ["Total payable", preview.data?.total_payable],
        ["First EMI", null],
      ].map(([label, value]) => (
        <div key={label} className={cn("flex flex-col gap-1", compact ? "px-4 py-3" : "px-5 py-4")}>
          <span className="eyebrow">{label}</span>
          {label === "First EMI" ? (
            <span className={cn("font-medium tracking-[-0.02em] text-ink", compact ? "text-[17px]" : "text-[20px]")}>
              {preview.data ? formatDayMonth(preview.data.first_due_date) : "—"}
            </span>
          ) : (
            <span className={cn("font-medium tracking-[-0.02em] text-ink tabular-nums", compact ? "text-[17px]" : "text-[20px]")}>
              {value ? <Money value={value} quietSymbol /> : "—"}
            </span>
          )}
        </div>
      ))}
    </div>
  );
  const rows = preview.data?.installments ?? [];
  const schedule = (
    <div className={preview.isFetching ? "opacity-60 transition-opacity" : ""}>
      <ol aria-label="Repayment schedule preview" className={cn("divide-y divide-rule", !compact && "@lg:hidden")}>
        {rows.map((row) => (
          <li key={row.installment_no} className={cn("flex items-center gap-3", compact ? "px-4 py-2.5" : "px-5 py-3")}>
            <span className="w-5 shrink-0 font-mono text-[12px] text-faint tabular-nums">{row.installment_no}</span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[14px] text-ink">{formatDate(row.due_date)}</span>
              <span className="text-[12px] text-faint">
                from <Money value={row.opening_balance} />
              </span>
            </span>
            <span className="flex shrink-0 flex-col items-end gap-0.5">
              <Money value={row.amount_due} className="text-[14px] text-ink" />
              <span className="text-[12px] text-faint">
                <Money value={row.interest_component} /> interest
              </span>
            </span>
          </li>
        ))}
      </ol>
      {!compact && (
        <table className="hidden w-full text-[13px] @lg:table">
          <caption className="sr-only">Repayment schedule preview</caption>
          <thead className="bg-sunk">
            <tr>
              {["No.", "Due", "Opening", "Principal", "Interest", "EMI"].map((label, index) => (
                <th key={label} scope="col" className={`h-9 px-4 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase ${index > 1 ? "text-right" : ""}`}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {rows.map((row) => (
              <tr key={row.installment_no}>
                <td className="h-10 px-4 tabular-nums text-dim">{row.installment_no}</td>
                <td className="px-4">{formatDate(row.due_date)}</td>
                <td className="px-4 text-right"><Money value={row.opening_balance} tone="dim" /></td>
                <td className="px-4 text-right"><Money value={row.principal_component} /></td>
                <td className="px-4 text-right"><Money value={row.interest_component} tone="dim" /></td>
                <td className="px-4 text-right"><Money value={row.amount_due} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  if (compact) {
    return (
      <div className="flex flex-col gap-3">
        {kpis}
        <div className="max-h-64 overflow-y-auto rounded-lg border border-rule" data-lenis-prevent>
          {schedule}
        </div>
      </div>
    );
  }
  return (
    <>
      {kpis}
      <SectionCard flush eyebrow="Schedule" title="Repayment schedule" description="Interest on the reducing balance; the last instalment absorbs rounding.">
        {schedule}
      </SectionCard>
    </>
  );
}
