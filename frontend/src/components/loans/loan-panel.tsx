"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { RecordCard } from "@/components/branch/record-card";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { FactList } from "@/components/layout/section-card";
import { Segmented } from "@/components/layout/segmented";
import { Money } from "@/components/money/money";
import { ModeChip } from "@/components/status/mode-chip";
import { StatusChip } from "@/components/status/status-chip";
import { loanQueries } from "@/features/loans/api";
import { formatDate, formatDateTime, formatDayMonth, formatTime } from "@/lib/dates";
import { moneyRatio } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ID, LoanSummary, Repayment } from "@/types/domain";

type Tab = "schedule" | "repayments";

interface LoanPanelProps {
  loan: LoanSummary;
  /** Where a repayment row opens its receipt; `null` shows the row without a link. */
  receiptHref: (repayment: Repayment) => string | null;
  actions?: ReactNode;
}

/** A loan at a glance — balance, progress, next due — with its schedule and repayment history. */
export function LoanPanel({ loan, receiptHref, actions }: LoanPanelProps) {
  const [tab, setTab] = useState<Tab>("schedule");
  const paidRatio = moneyRatio(loan.amount_paid, loan.total_payable);

  return (
    <article className="overflow-hidden rounded-xl border border-rule bg-raised">
      <header className="flex flex-wrap items-start justify-between gap-3 px-5 pt-4.5 pb-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="eyebrow">Loan</p>
          <h3 className="font-mono text-[14px] text-ink">{loan.loan_number}</h3>
          <p className="text-[12.5px] text-dim">
            <Money value={loan.principal} whole /> at {loan.annual_interest_rate}% for {loan.tenure_months} months · disbursed{" "}
            {formatDate(loan.disbursed_on)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusChip kind="loan" status={loan.status} />
          {actions}
        </div>
      </header>

      <div className="px-5 pb-4">
        <div className="flex items-baseline justify-between text-[12.5px] text-dim">
          <span>
            Paid <Money value={loan.amount_paid} whole className="text-ink" /> of <Money value={loan.total_payable} whole />
          </span>
          <span className="tabular-nums">{Math.round(paidRatio * 100)}%</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sunk" aria-hidden>
          <div className="h-full rounded-full bg-st-settled transition-[width] duration-700" style={{ width: `${paidRatio * 100}%` }} />
        </div>
      </div>

      <FactList
        className="rounded-none border-x-0 max-sm:grid-cols-2 max-sm:[&>:last-child]:col-span-2"
        columns={3}
        items={[
          ["Outstanding", <Money key="o" value={loan.outstanding} />],
          ["EMI", <Money key="e" value={loan.emi_amount} />],
          [
            "Next due",
            loan.next_due_date ? (
              <span key="n" className="flex flex-wrap items-baseline gap-x-2">
                {formatDate(loan.next_due_date)}
                {loan.overdue_amount !== "0.00" && (
                  <span className="text-st-short-fg">
                    <Money value={loan.overdue_amount} /> overdue
                  </span>
                )}
              </span>
            ) : (
              "—"
            ),
          ],
        ]}
      />

      <div className="flex flex-col gap-3 px-5 pt-4 pb-5">
        <Segmented<Tab>
          label="Loan detail"
          size="sm"
          value={tab}
          onChange={setTab}
          options={[
            { value: "schedule", label: "Schedule" },
            { value: "repayments", label: "Repayments" },
          ]}
        />
        {tab === "schedule" ? <Schedule loanId={loan.id} /> : <Repayments loanId={loan.id} receiptHref={receiptHref} />}
      </div>
    </article>
  );
}

function Schedule({ loanId }: { loanId: ID }) {
  const schedule = useQuery(loanQueries.schedule(loanId));
  if (schedule.isPending) return <CardListSkeleton count={3} />;
  if (schedule.isError) return <ErrorState error={schedule.error} onRetry={() => void schedule.refetch()} compact />;

  return (
    // Phones stop mid-row so the list reads as scrollable rather than ending in a blank strip.
    <div className="max-h-80 overflow-y-auto rounded-lg border border-rule max-sm:max-h-[340px]" data-lenis-prevent>
      <table className="w-full text-[13px] max-sm:hidden">
        <caption className="sr-only">Repayment schedule</caption>
        <thead className="sticky top-0 bg-sunk">
          <tr>
            {["No.", "Due", "Amount", "Paid", "Status"].map((label, index) => (
              <th
                key={label}
                scope="col"
                className={cn(
                  "h-8 px-3 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase",
                  (index === 2 || index === 3) && "text-right",
                )}
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {schedule.data.map((row) => (
            <tr key={row.id} className={cn(row.status === "PAID" && "text-dim")}>
              <td className="h-10 px-3 tabular-nums">{row.installment_no}</td>
              <td className="px-3">{formatDayMonth(row.due_date)}</td>
              <td className="px-3 text-right">
                <Money value={row.amount_due} />
              </td>
              <td className="px-3 text-right">
                <Money value={row.amount_paid} tone={row.amount_paid === "0.00" ? "dim" : "none"} />
              </td>
              <td className="px-3">
                <StatusChip kind="installment" status={row.status} isOverdue={row.is_overdue} dueDate={row.due_date} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ol aria-label="Repayment schedule" className="divide-y divide-rule sm:hidden">
        {schedule.data.map((row) => (
          <li key={row.id} className={cn("flex items-center gap-3 px-3.5 py-2.5", row.status === "PAID" && "text-dim")}>
            <span className="w-5 shrink-0 font-mono text-[12px] text-faint tabular-nums">{row.installment_no}</span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="text-[13.5px]">{formatDate(row.due_date)}</span>
              <StatusChip kind="installment" status={row.status} isOverdue={row.is_overdue} dueDate={row.due_date} size="sm" />
            </span>
            <span className="flex shrink-0 flex-col items-end gap-0.5">
              <Money value={row.amount_due} className="text-[13.5px]" />
              {row.amount_paid !== "0.00" && row.amount_paid !== row.amount_due && (
                <span className="text-[12px] text-faint">
                  paid <Money value={row.amount_paid} />
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Repayments({ loanId, receiptHref }: { loanId: ID; receiptHref: LoanPanelProps["receiptHref"] }) {
  const repayments = useQuery(loanQueries.repayments(loanId, { page_size: 50 }));
  if (repayments.isPending) return <CardListSkeleton count={3} />;
  if (repayments.isError) return <ErrorState error={repayments.error} onRetry={() => void repayments.refetch()} compact />;
  if (repayments.data.results.length === 0) {
    return <EmptyState compact title="No repayments yet." description="The first receipt will appear here." />;
  }

  return (
    <ul className="divide-y divide-rule overflow-hidden rounded-lg border border-rule">
      {repayments.data.results.map((repayment) => {
        const href = receiptHref(repayment);
        const content = <RepaymentRow repayment={repayment} />;
        return (
          <li key={repayment.id}>
            {href ? (
              <Link href={href} className="flex items-center justify-between gap-3 px-3.5 py-3 transition-colors hover:bg-sunk/60">
                {content}
              </Link>
            ) : (
              <div className="flex items-center justify-between gap-3 px-3.5 py-3">{content}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function RepaymentRow({ repayment }: { repayment: Repayment }) {
  const collectedBy = repayment.agent_name ?? (repayment.mode === "UPI" ? "Customer (UPI)" : null);
  return (
    <>
      <div className="w-full sm:hidden">
        <RecordCard
          mono
          title={repayment.receipt_number}
          amount={<Money value={repayment.amount} strike={repayment.status === "VOIDED"} />}
          subtitle={<ModeChip mode={repayment.mode} className="text-[10.5px]" />}
          badge={<StatusChip kind="collection" status={repayment.status} size="sm" />}
          meta={[`${formatDayMonth(repayment.collected_at)}, ${formatTime(repayment.collected_at)}`, collectedBy]}
        />
      </div>
      <span className="flex min-w-0 flex-col gap-0.5 max-sm:hidden">
        <span className="truncate font-mono text-[12.5px] text-ink">{repayment.receipt_number}</span>
        <span className="text-[12px] text-faint">
          {formatDateTime(repayment.collected_at)}
          {collectedBy && ` · ${collectedBy}`}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1 max-sm:hidden">
        <Money value={repayment.amount} strike={repayment.status === "VOIDED"} className="text-[13.5px] text-ink" />
        <span className="flex items-center gap-2">
          <ModeChip mode={repayment.mode} />
          <StatusChip kind="collection" status={repayment.status} size="sm" />
        </span>
      </span>
    </>
  );
}
