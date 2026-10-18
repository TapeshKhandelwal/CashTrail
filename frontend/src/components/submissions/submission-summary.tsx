import Link from "next/link";

import { FactList, SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { StatusChip } from "@/components/status/status-chip";
import { formatDateTime, formatTime, formatDayMonth } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { isNegative, isZero, negateMoney } from "@/lib/money";
import { DISCREPANCY_KIND_LABEL, DISCREPANCY_REASON_LABEL, type CashSubmissionDetail, type ID } from "@/types/domain";

/** Expected minus received from the API → counted minus expected for display (short is negative). */
export const countedVariance = (difference: string) => negateMoney(difference);

/** Whether the agent counted the notes before handing over; the branch's count is kept apart. */
function agentCounted(submission: CashSubmissionDetail): boolean {
  return submission.denominations !== null;
}

/** The facts of a hand-over: amounts, who and when, its outcome and any discrepancy raised. */
export function SubmissionFacts({ submission }: { submission: CashSubmissionDetail }) {
  const reviewed = submission.received_amount !== null;
  const variance = submission.difference ? countedVariance(submission.difference) : null;
  const selfCount = agentCounted(submission);

  return (
    <SectionCard
      flush
      tone={submission.status === "SUBMITTED" ? "submitted" : submission.status === "REJECTED" ? "rejected" : "received"}
      eyebrow={submission.submission_number}
      title={`${submission.agent_name} · ${countOf(submission.collection_count, "receipt")}`}
      actions={<StatusChip kind="submission" status={submission.status} difference={submission.difference} wash />}
    >
      <FactList
        className="rounded-none border-0 max-sm:grid-cols-2 max-sm:[&>:nth-child(n+5)]:col-span-2 md:max-lg:grid-cols-2"
        columns={3}
        items={[
          ["Receipted", <Money key="e" value={submission.expected_amount} />],
          selfCount
            ? ["Agent's count", <Money key="d" value={submission.declared_amount} />]
            : ["Agent's count", <span key="d" className="text-faint">Not counted</span>],
          [
            "Branch counted",
            reviewed ? (
              <span key="r" className="flex flex-wrap items-baseline gap-x-2">
                <Money value={submission.received_amount ?? "0.00"} />
                {variance && !isZero(variance) && (
                  <Money value={variance} signed tone="direction" className="text-[12.5px]" />
                )}
              </span>
            ) : (
              <span key="r" className="text-faint">
                {submission.status === "REJECTED" ? "Not accepted" : "Not yet counted"}
              </span>
            ),
          ],
          ["Handed over", formatDateTime(submission.submitted_at)],
          ["Reviewed", submission.reviewed_at ? `${formatDateTime(submission.reviewed_at)} · ${submission.reviewed_by_name}` : "—"],
          ["Deposit", submission.deposit_number ? <span key="dep" className="font-mono">{submission.deposit_number}</span> : "—"],
        ]}
      />
      {(submission.rejection_reason || submission.review_remarks) && (
        <p className="border-t border-rule px-5 py-3.5 text-[13.5px] text-dim">
          <span className="eyebrow mr-2">{submission.rejection_reason ? "Rejected" : "Remarks"}</span>
          {submission.rejection_reason || submission.review_remarks}
        </p>
      )}
      {submission.discrepancies.map((item) => (
        <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-rule bg-st-short/5 px-5 py-3.5">
          <div className="flex flex-col gap-0.5">
            <span className="text-[13.5px] text-ink">
              {DISCREPANCY_KIND_LABEL[item.kind]} · {DISCREPANCY_REASON_LABEL[item.reason_code]}
            </span>
            {item.notes && <span className="text-[12.5px] text-dim">{item.notes}</span>}
          </div>
          <span className="flex items-center gap-3">
            <Money value={item.amount} tone={item.direction === "SHORT" ? "short" : "excess"} />
            <StatusChip kind="discrepancy" status={item.status} direction={item.direction} size="sm" />
          </span>
        </div>
      ))}
    </SectionCard>
  );
}

/** The receipts inside a hand-over. */
export function SubmissionReceipts({ submission, receiptHref }: { submission: CashSubmissionDetail; receiptHref: (id: ID) => string }) {
  return (
    <SectionCard flush eyebrow="Receipts" title="What was handed over">
      <ul className="divide-y divide-rule">
        {submission.collections.map((receipt) => (
          <li key={receipt.id}>
            <Link href={receiptHref(receipt.id)} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-sunk/50">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="truncate text-[14px] text-ink">{receipt.customer_name}</span>
                <span className="truncate font-mono text-[11.5px] text-faint">
                  <span className="max-sm:hidden">
                    {formatDayMonth(receipt.collected_at)} {formatTime(receipt.collected_at)} ·{" "}
                  </span>
                  {receipt.receipt_number}
                </span>
              </span>
              <span className="flex shrink-0 flex-col items-end gap-0.5">
                <Money value={receipt.amount} className={isNegative(receipt.amount) ? "text-st-short-fg" : "text-ink"} />
                <span className="font-mono text-[11.5px] text-faint sm:hidden">
                  {formatDayMonth(receipt.collected_at)} {formatTime(receipt.collected_at)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
