"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ConfirmDialog, ConfirmFacts } from "@/components/feedback/confirm-dialog";
import { QueryView } from "@/components/feedback/query-view";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { StickyActionBar } from "@/components/layout/sticky-action-bar";
import { DenominationCounter } from "@/components/money/denomination-counter";
import { compactDenominations, denominationsTotal } from "@/components/money/denominations";
import { Money } from "@/components/money/money";
import { VarianceMeter, varianceLabel, varianceOf } from "@/components/money/variance-meter";
import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { SubmissionFacts, SubmissionReceipts } from "@/components/submissions/submission-summary";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { submissionQueries, useApproveSubmission, useRejectSubmission } from "@/features/submissions/api";
import { formatDateTime } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { isZero } from "@/lib/money";
import {
  DISCREPANCY_REASON_LABEL,
  type CashSubmissionDetail,
  type Denominations,
  type DiscrepancyReasonCode,
  type ID,
} from "@/types/domain";

const CASH_REASONS: DiscrepancyReasonCode[] = ["COUNTING_ERROR", "AGENT_SHORTAGE", "OTHER"];

export function SubmissionVerify({ id }: { id: ID }) {
  const submission = useQuery(submissionQueries.detail(id));
  return (
    <QueryView query={submission} loading={<DetailSkeleton />} errorTitle="We couldn't load this hand-over.">
      {(data) =>
        data.status === "SUBMITTED" ? (
          <CountScreen submission={data} />
        ) : (
          <>
            <PageCrumb label={data.submission_number} />
            <PageHeader eyebrow={`${data.branch_code} · Hand-over`} title={data.submission_number} />
            <div className="flex flex-col gap-5">
              <SubmissionFacts submission={data} />
              <SubmissionReceipts submission={data} receiptHref={(receipt) => `/app/branch/collections/${receipt}`} />
            </div>
          </>
        )
      }
    </QueryView>
  );
}

function CountScreen({ submission }: { submission: CashSubmissionDetail }) {
  const [counts, setCounts] = useState<Denominations>({});
  const [reason, setReason] = useState<DiscrepancyReasonCode | "">("");
  const [remarks, setRemarks] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const approve = useApproveSubmission({ successMessage: (result) => `${result.submission_number} accepted` });

  const counted = denominationsTotal(counts);
  const hasCount = !isZero(counted);
  const variance = varianceOf(submission.expected_amount, counted);
  const differs = hasCount && variance.state !== "match";
  const ready = hasCount && (!differs || (reason !== "" && remarks.trim().length >= 5));

  const declared = varianceOf(submission.expected_amount, submission.declared_amount);
  const accept = (
    <Button size="xl" className="w-full" disabled={!ready || approve.isPending} onClick={() => setConfirming(true)}>
      {approve.isPending && <Loader2 className="animate-spin" />}
      <span>
        {!hasCount ? "Count the cash to continue" : differs ? "Accept with discrepancy" : <>Accept <Money value={counted} /></>}
      </span>
    </Button>
  );

  return (
    <>
      <PageCrumb label="Count cash" />
      <PageHeader
        eyebrow={`${submission.branch_code} · Count cash`}
        title={`${submission.agent_name}'s hand-over`}
        description={`${submission.submission_number} · ${countOf(submission.collection_count, "receipt")} · handed over ${formatDateTime(submission.submitted_at)}`}
        actions={
          <Button variant="destructive" onClick={() => setRejecting(true)}>
            Reject
          </Button>
        }
      />

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_420px] lg:grid-rows-[auto_1fr] lg:gap-x-6">
        <div className="grid-ruled grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1 px-4 py-4 sm:px-5">
            <span className="eyebrow">Receipted</span>
            <Money value={submission.expected_amount} quietSymbol className="figure max-sm:text-[22px]" />
            <span className="text-[12.5px] text-dim">what the receipts add up to</span>
          </div>
          <div className="flex min-w-0 flex-col gap-1 px-4 py-4 sm:px-5">
            <span className="eyebrow">Agent&apos;s count</span>
            {submission.denominations === null ? (
              <>
                <span className="figure text-faint max-sm:text-[22px]">Not counted</span>
                <span className="text-[12.5px] text-dim">handed over as receipted</span>
              </>
            ) : (
              <>
                <Money value={submission.declared_amount} quietSymbol className="figure max-sm:text-[22px]" />
                <span className="text-[12.5px] text-dim">
                  {isZero(declared.difference) ? "matches the receipts" : varianceLabel(declared.state, declared.difference)}
                </span>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-5 lg:sticky lg:top-24 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          <SectionCard eyebrow="Your count" title="Count the cash in front of you" description="Count it yourself; don't copy the agent's figure.">
            <DenominationCounter value={counts} onChange={setCounts} />
          </SectionCard>

          {hasCount && <VarianceMeter expected={submission.expected_amount} counted={counted} expectedLabel="Receipted" countedLabel="Counted" />}

          {differs && (
            <SectionCard tone="short" eyebrow="Discrepancy" title={`Record why it is ${variance.state === "short" ? "short" : "over"}`}>
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="reason">Reason</Label>
                  <Select value={reason} onValueChange={(value) => setReason(value as DiscrepancyReasonCode)}>
                    <SelectTrigger id="reason" className="w-full">
                      <SelectValue placeholder="Choose a reason" />
                    </SelectTrigger>
                    <SelectContent>
                      {CASH_REASONS.map((code) => (
                        <SelectItem key={code} value={code}>
                          {DISCREPANCY_REASON_LABEL[code]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="remarks">What happened</Label>
                  <Textarea
                    id="remarks"
                    rows={3}
                    placeholder="e.g. Counted twice with the agent present; the agent cannot account for the difference."
                    value={remarks}
                    onChange={(event) => setRemarks(event.target.value)}
                  />
                </div>
              </div>
            </SectionCard>
          )}

          <div className="max-md:hidden">{accept}</div>
        </div>

        <SubmissionReceipts submission={submission} receiptHref={(receipt) => `/app/branch/collections/${receipt}`} />
      </div>

      <div className="md:hidden">
        <StickyActionBar>
          {hasCount && (
            <div className="flex items-center justify-between gap-3 text-[13px]">
              <span className="text-dim">
                Counted <Money value={counted} className="font-medium text-ink" />
              </span>
              {differs ? (
                <span className={variance.state === "short" ? "text-st-short-fg" : "text-st-excess-fg"}>
                  {varianceLabel(variance.state, variance.difference)}
                </span>
              ) : (
                <span className="text-st-settled-fg">Matches the receipts</span>
              )}
            </div>
          )}
          {accept}
        </StickyActionBar>
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title={differs ? "Accept with a discrepancy?" : "Accept this cash?"}
        description={
          differs
            ? `A ${variance.state === "short" ? "shortage" : "surplus"} of the difference is recorded against ${submission.agent_name}. The receipts move to the branch.`
            : "The receipts move to the branch's cash, ready to deposit."
        }
        confirmLabel={differs ? "Accept and record discrepancy" : "Accept"}
        loading={approve.isPending}
        onConfirm={() =>
          approve.mutate(
            {
              id: submission.id,
              received_amount: counted,
              denominations: compactDenominations(counts),
              reason_code: differs && reason ? reason : undefined,
              remarks: remarks.trim() || undefined,
            },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <ConfirmFacts
          rows={[
            ["Receipted", <Money key="e" value={submission.expected_amount} />],
            ["Counted", <Money key="c" value={counted} />],
            ["Difference", <Money key="d" value={variance.difference} signed tone="direction" />],
          ]}
        />
      </ConfirmDialog>

      <RejectDialog submission={submission} open={rejecting} onOpenChange={setRejecting} />
    </>
  );
}

function RejectDialog({ submission, open, onOpenChange }: { submission: CashSubmissionDetail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [reason, setReason] = useState("");
  const reject = useRejectSubmission({ successMessage: (result) => `${result.submission_number} returned to the agent` });

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Reject this hand-over?"
      description={`The cash stays with ${submission.agent_name} and the receipts go back to them to hand over again. Nothing is recorded against the branch.`}
      footer={
        <Button
          variant="destructive-solid"
          disabled={reason.trim().length < 5 || reject.isPending}
          onClick={() => reject.mutate({ id: submission.id, reason: reason.trim() }, { onSuccess: () => onOpenChange(false) })}
        >
          {reject.isPending && <Loader2 className="animate-spin" />}
          Reject hand-over
        </Button>
      }
    >
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="reject-reason">Reason</Label>
        <Textarea
          id="reject-reason"
          rows={3}
          placeholder="e.g. Cash and receipts do not tally; recount and resubmit with the receipt copies."
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </div>
    </ResponsiveDialog>
  );
}
