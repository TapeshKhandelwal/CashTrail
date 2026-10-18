"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { QueryView } from "@/components/feedback/query-view";
import { CardListSkeleton, DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { StatusChip } from "@/components/status/status-chip";
import { SubmissionFacts } from "@/components/submissions/submission-summary";
import { submissionQueries } from "@/features/submissions/api";
import { formatDateTime } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { isNegative } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { ID, SubmissionStatus } from "@/types/domain";

import { ReceiptSummary } from "./receipt-summary";

export function AgentSubmissions() {
  const list = useQuery(submissionQueries.list({ page_size: 50, ordering: "-submitted_at" }));

  return (
    <div className="mx-auto w-full max-w-[760px]">
      <PageHeader eyebrow="Cash" title="Hand-overs" description="Every time you handed cash to the branch, and what the count found." />
      {list.isPending ? (
        <CardListSkeleton count={5} />
      ) : list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} bordered />
      ) : list.data.results.length === 0 ? (
        <EmptyState bordered title="No hand-overs yet." />
      ) : (
        <ul className="rows-enter divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
          {list.data.results.map((item) => (
            <li key={item.id}>
              <Link
                href={`/app/agent/handover/submissions/${item.id}`}
                className="flex items-start justify-between gap-3 px-4 py-3.5 transition-colors outline-none hover:bg-sunk/50 focus-visible:bg-sunk sm:px-5"
              >
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="truncate font-mono text-[12.5px] text-ink">{item.submission_number}</span>
                  <span className="text-[12px] text-faint">
                    {formatDateTime(item.submitted_at)} · {countOf(item.collection_count, "receipt")}
                  </span>
                  <StatusChip kind="submission" status={item.status} difference={item.difference} size="sm" />
                </span>
                <Money value={item.received_amount ?? item.declared_amount} className="shrink-0 text-[14px] text-ink" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const OUTCOME: Record<SubmissionStatus, string> = {
  SUBMITTED: "Waiting to be counted",
  APPROVED: "Counted and accepted",
  APPROVED_WITH_DISCREPANCY: "Accepted with a difference",
  REJECTED: "Not accepted",
};

export function AgentSubmission({ id }: { id: ID }) {
  const submission = useQuery(submissionQueries.detail(id));
  return (
    <QueryView query={submission} loading={<DetailSkeleton />} errorTitle="We couldn't load this hand-over.">
      {(data) => (
        <div className="mx-auto w-full max-w-[760px]">
          <PageCrumb label={data.submission_number} />
          <PageHeader eyebrow="Hand-over" title={OUTCOME[data.status]} />
          <div className="flex flex-col gap-5">
            <SubmissionFacts submission={data} />
            <SectionCard flush eyebrow="Receipts" title="What was handed over">
              <ul className="divide-y divide-rule">
                {data.collections.map((receipt) => (
                  <li key={receipt.id}>
                    <Link
                      href={`/app/agent/receipts/${receipt.id}`}
                      className="flex items-center gap-3 px-4 py-3 transition-colors outline-none hover:bg-sunk/50 focus-visible:bg-sunk sm:px-5"
                    >
                      <ReceiptSummary receipt={receipt} />
                      <Money
                        value={receipt.amount}
                        className={cn("shrink-0", isNegative(receipt.amount) ? "text-st-short-fg" : "text-ink")}
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            </SectionCard>
          </div>
        </div>
      )}
    </QueryView>
  );
}
