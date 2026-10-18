"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, History, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";

import { ConfirmDialog, ConfirmFacts } from "@/components/feedback/confirm-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { StickyActionBar } from "@/components/layout/sticky-action-bar";
import { DenominationCounter } from "@/components/money/denomination-counter";
import { compactDenominations, denominationsTotal } from "@/components/money/denominations";
import { Money } from "@/components/money/money";
import { VarianceMeter, varianceOf } from "@/components/money/variance-meter";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { collectionQueries } from "@/features/collections/api";
import { submissionQueries, useCreateSubmission } from "@/features/submissions/api";
import { formatDateTime } from "@/lib/dates";
import { formatCount, countOf } from "@/lib/format";
import { isZero, sumMoney } from "@/lib/money";
import type { Collection, Denominations, ID } from "@/types/domain";

import { ReceiptSummary } from "./receipt-summary";

export function HandoverFlow() {
  const pending = useQuery(submissionQueries.list({ status: ["SUBMITTED"], page_size: 1 }));
  const cash = useQuery(collectionQueries.list({ status: ["COLLECTED"], mode: "CASH", page_size: 100, ordering: "collected_at" }));

  return (
    <div className="mx-auto w-full max-w-[620px]">
      <PageHeader
        eyebrow="Cash"
        title="Hand over cash"
        description="Give the branch the cash for your receipts. The branch manager counts it before accepting it."
        actions={
          <Button asChild variant="ghost" size="sm" className="max-sm:-ml-2">
            <Link href="/app/agent/handover/submissions">
              <History data-icon="inline-start" />
              Past hand-overs
            </Link>
          </Button>
        }
      />
      {pending.isPending || cash.isPending ? (
        <CardListSkeleton count={4} />
      ) : pending.isError ? (
        <ErrorState error={pending.error} onRetry={() => void pending.refetch()} bordered />
      ) : cash.isError ? (
        <ErrorState error={cash.error} onRetry={() => void cash.refetch()} bordered />
      ) : pending.data.results[0] ? (
        <AwaitingCount submission={pending.data.results[0]} heldCount={cash.data.count} />
      ) : cash.data.results.length === 0 ? (
        <EmptyState
          bordered
          illustration="settled"
          title="Nothing to hand over."
          description="Every cash receipt you recorded is already with the branch."
          action={
            <Button asChild variant="outline">
              <Link href="/app/agent">Back to today</Link>
            </Button>
          }
        />
      ) : (
        <HandoverForm receipts={cash.data.results} />
      )}
    </div>
  );
}

function AwaitingCount({
  submission,
  heldCount,
}: {
  submission: { id: ID; submission_number: string; expected_amount: string; declared_amount: string; submitted_at: string; collection_count: number };
  heldCount: number;
}) {
  return (
    <div className="flex flex-col gap-4">
      <SectionCard tone="submitted" eyebrow="With the branch" title="Waiting to be counted">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between sm:gap-4">
            <div className="flex min-w-0 flex-col gap-1">
              <span className="truncate font-mono text-[12.5px] text-ink">{submission.submission_number}</span>
              <span className="text-[12.5px] text-faint">
                {countOf(submission.collection_count, "receipt")} · handed over {formatDateTime(submission.submitted_at)}
              </span>
            </div>
            <Money
              value={submission.declared_amount}
              quietSymbol
              className="shrink-0 text-[26px] font-medium tracking-[-0.02em] text-ink max-sm:order-first"
            />
          </div>
          <StatusChip kind="submission" status="SUBMITTED" wash />
        </div>
      </SectionCard>
      <p className="text-[13px] leading-relaxed text-dim">
        The branch counts one hand-over at a time.
        {heldCount > 0 && ` You are carrying ${countOf(heldCount, "more receipt")}; hand them over once this count is done.`}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button asChild variant="outline" className="max-sm:h-11">
          <Link href={`/app/agent/handover/submissions/${submission.id}`}>
            Open hand-over
            <ArrowRight data-icon="inline-end" />
          </Link>
        </Button>
        <Button asChild variant="ghost" className="max-sm:h-11 md:hidden">
          <Link href="/app/agent">Back to today</Link>
        </Button>
      </div>
    </div>
  );
}

function HandoverForm({ receipts }: { receipts: Collection[] }) {
  const router = useRouter();
  const [excluded, setExcluded] = useState<Set<ID>>(new Set());
  const [counting, setCounting] = useState(false);
  const [counts, setCounts] = useState<Denominations>({});
  const [confirming, setConfirming] = useState(false);
  // Navigate from the hook's own onSuccess: the refetch it triggers replaces this form with the
  // "waiting to be counted" state, and per-call callbacks never fire once the form unmounts.
  const create = useCreateSubmission({
    handledErrors: ["PENDING_SUBMISSION_EXISTS"],
    onSuccess: (submission) => router.push(`/app/agent/handover/submissions/${submission.id}`),
  });

  const selected = useMemo(() => receipts.filter((receipt) => !excluded.has(receipt.id)), [receipts, excluded]);
  const expected = sumMoney(selected.map((receipt) => receipt.amount));
  const counted = denominationsTotal(counts);
  // The receipts are what the agent owes the branch; counting notes first is optional and only
  // changes the declared figure when the agent actually counted.
  const selfCounted = counting && !isZero(counted);
  const declared = selfCounted ? counted : expected;
  const variance = varianceOf(expected, declared);
  const canSubmit = selected.length > 0;

  const toggle = (id: ID) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(event) => {
        event.preventDefault();
        if (canSubmit) setConfirming(true);
      }}
    >
      <SectionCard
        eyebrow={`${formatCount(selected.length)} of ${countOf(receipts.length, "receipt")}`}
        title="Cash receipts you are carrying"
        description="Untick any receipt you are keeping for a later hand-over."
        flush
        footer={
          <div className="flex items-center justify-between text-[13.5px]">
            <span className="text-dim">To hand over</span>
            <Money value={expected} className="text-[15px] font-medium text-ink" />
          </div>
        }
      >
        <ul className="divide-y divide-rule">
          {receipts.map((receipt) => (
            <li key={receipt.id}>
              <label className="flex cursor-pointer items-center gap-3.5 px-4 py-3 transition-colors hover:bg-sunk/50 sm:px-5">
                <Checkbox checked={!excluded.has(receipt.id)} onCheckedChange={() => toggle(receipt.id)} aria-label={receipt.receipt_number} />
                <ReceiptSummary receipt={receipt} />
                <Money value={receipt.amount} className="shrink-0 text-[14px] text-ink" />
              </label>
            </li>
          ))}
        </ul>
      </SectionCard>

      <ol className="grid-ruled grid-cols-1 sm:grid-cols-3">
        {[
          ["1", "Hand over", "Give the cash and these receipts to your branch manager."],
          ["2", "Branch counts", "The manager counts every note and compares it with the receipts."],
          ["3", "Accepted", "Any difference is recorded against this hand-over, never hidden."],
        ].map(([step, title, body]) => (
          <li key={step} className="flex gap-3 px-5 py-4">
            <span className="font-mono text-[11px] text-faint">{step}</span>
            <span className="flex flex-col gap-0.5">
              <span className="text-[13.5px] text-ink">{title}</span>
              <span className="text-[12.5px] leading-relaxed text-dim">{body}</span>
            </span>
          </li>
        ))}
      </ol>

      {counting ? (
        <SectionCard
          eyebrow="Optional"
          title="Your own count"
          description="Count the notes before you hand them over. The branch's count is the one that is recorded."
          actions={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setCounting(false);
                setCounts({});
              }}
            >
              Skip
            </Button>
          }
        >
          <DenominationCounter
            value={counts}
            onChange={setCounts}
            fillAmount={expected}
            fillLabel="Fill from receipts"
            className="max-sm:-mx-5 max-sm:-mb-5 max-sm:rounded-none max-sm:border-x-0 max-sm:border-b-0"
          />
          {selfCounted && <VarianceMeter expected={expected} counted={counted} expectedLabel="Receipted" countedLabel="In hand" className="mt-4" />}
        </SectionCard>
      ) : (
        <button
          type="button"
          onClick={() => setCounting(true)}
          className="flex items-center justify-between gap-4 rounded-xl border border-dashed border-rule-strong px-5 py-4 text-left transition-colors hover:border-ink/25 hover:bg-sunk/50"
        >
          <span className="flex flex-col gap-0.5">
            <span className="text-[14px] text-ink">Count your cash first</span>
            <span className="text-[12.5px] text-dim">Optional. Catch a shortfall before the branch does.</span>
          </span>
          <ArrowRight aria-hidden className="size-4 shrink-0 text-faint" />
        </button>
      )}

      <StickyActionBar>
        <Button type="submit" size="xl" className="w-full" disabled={!canSubmit || create.isPending}>
          {create.isPending && <Loader2 className="animate-spin" />}
          <span>
            Hand over <Money value={declared} />
          </span>
        </Button>
      </StickyActionBar>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Hand this cash to the branch?"
        description={
          variance.state === "match"
            ? "The branch manager counts it before accepting it. Until then the cash stays your responsibility."
            : "Your count does not match the receipts. The branch counts it again and records the difference against this hand-over."
        }
        confirmLabel="Hand over"
        loading={create.isPending}
        onConfirm={() =>
          create.mutate(
            {
              collection_ids: selected.map((receipt) => receipt.id),
              declared_amount: declared,
              denominations: selfCounted ? compactDenominations(counts) : null,
            },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <ConfirmFacts
          rows={[
            ["Receipts", formatCount(selected.length)],
            ["Receipted", <Money key="e" value={expected} />],
            ...(selfCounted ? ([["Your count", <Money key="c" value={counted} />]] as [string, ReactNode][]) : []),
          ]}
        />
      </ConfirmDialog>
    </form>
  );
}
