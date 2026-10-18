"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { QueryView } from "@/components/feedback/query-view";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { FactList, SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { MoneyInput } from "@/components/money/money-input";
import { useSession } from "@/components/providers/session-provider";
import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { depositQueries, useFailDeposit, useSettleDeposit } from "@/features/deposits/api";
import { formatDate, formatDateTime, todayIST } from "@/lib/dates";
import { formatCount } from "@/lib/format";
import { compareMoney, isZero, negateMoney, parseMoneyInput } from "@/lib/money";
import { cn } from "@/lib/utils";
import {
  DISCREPANCY_KIND_LABEL,
  DISCREPANCY_REASON_LABEL,
  type DepositDetail,
  type DiscrepancyReasonCode,
  type ID,
} from "@/types/domain";

interface DepositDetailViewProps {
  id: ID;
  /** Where a hand-over opens; omit for roles without access to the branch desk. */
  submissionHref?: (id: ID) => string;
}

export function DepositDetailView({ id, submissionHref }: DepositDetailViewProps) {
  const deposit = useQuery(depositQueries.detail(id));
  return (
    <QueryView query={deposit} loading={<DetailSkeleton />} errorTitle="We couldn't load this deposit.">
      {(data) => <DepositBody deposit={data} submissionHref={submissionHref} />}
    </QueryView>
  );
}

function DepositBody({ deposit, submissionHref }: { deposit: DepositDetail; submissionHref?: (id: ID) => string }) {
  const user = useSession();
  const [settling, setSettling] = useState(false);
  const [failing, setFailing] = useState(false);
  const canConfirm = deposit.status === "PENDING" && (user.role === "FINANCE" || user.role === "ADMIN");
  // Maker-checker: whoever recorded the deposit cannot confirm its outcome.
  const ownDeposit = deposit.created_by === user.id;
  const canSettle = canConfirm && !ownDeposit;
  const gateway = deposit.source === "GATEWAY";

  return (
    <>
      <PageCrumb label={deposit.deposit_number} />
      <PageHeader
        eyebrow={gateway ? "Gateway settlement" : `${deposit.branch_code} · Bank deposit`}
        title={deposit.deposit_number}
        description={`${deposit.bank_account.bank_name} ${deposit.bank_account.masked_account_number} · reference ${deposit.reference_number}`}
        actions={
          canSettle ? (
            <>
              <Button variant="destructive" onClick={() => setFailing(true)}>
                Mark failed
              </Button>
              <Button onClick={() => setSettling(true)}>Confirm settlement</Button>
            </>
          ) : (
            canConfirm && (
              <p className="max-w-72 text-[13px] text-dim sm:text-right">You recorded this deposit, so someone else in finance confirms or fails it.</p>
            )
          )
        }
      >
        <StatusChip kind="deposit" status={deposit.status} isDelayed={deposit.is_delayed} daysPending={deposit.days_pending} withIcon wash />
      </PageHeader>

      <div className="flex flex-col gap-6">
        <ReconciliationChain deposit={deposit} />

        <div className="grid items-start gap-6 lg:grid-cols-2">
          <SectionCard flush eyebrow="Details" title="The deposit">
            <FactList
              className="rounded-none border-0 max-sm:grid-cols-2 max-sm:[&>:nth-child(n+5)]:col-span-2"
              columns={2}
              items={[
                ["Deposited on", formatDate(deposit.deposit_date)],
                ["Recorded by", deposit.created_by_name],
                ["Settled on", deposit.settled_on ? formatDate(deposit.settled_on) : "—"],
                ["Confirmed by", deposit.settled_by_name ?? "—"],
                ["Statement ref", deposit.settlement_reference ? <span key="s" className="font-mono">{deposit.settlement_reference}</span> : "—"],
                ["Receipts", formatCount(deposit.collections_count)],
              ]}
            />
            {(deposit.remarks || deposit.failure_reason) && (
              <p className="border-t border-rule px-5 py-3.5 text-[13.5px] text-dim">
                <span className="eyebrow mr-2">{deposit.failure_reason ? "Failed" : "Remarks"}</span>
                {deposit.failure_reason || deposit.remarks}
              </p>
            )}
          </SectionCard>

          <div className="flex flex-col gap-6">
            {deposit.submissions.length > 0 && (
              <SectionCard flush eyebrow="Hand-overs" title={deposit.status === "FAILED" ? "Returned to the branch" : "Cash on this slip"}>
                <ul className="divide-y divide-rule">
                  {deposit.submissions.map((item) => (
                    <li key={item.id}>
                      <SubmissionLine href={submissionHref?.(item.id)}>
                        <span className="flex min-w-0 flex-col gap-0.5">
                          <span className="truncate text-[14px] text-ink">{item.agent_name}</span>
                          <span className="font-mono text-[11.5px] wrap-anywhere text-faint">{item.submission_number}</span>
                        </span>
                        <Money value={item.received_amount ?? item.expected_amount} className="text-ink" />
                      </SubmissionLine>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
            {deposit.discrepancies.length > 0 && (
              <SectionCard flush tone="short" eyebrow="Raised" title="Discrepancies">
                <ul className="divide-y divide-rule">
                  {deposit.discrepancies.map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 px-5 py-3">
                      <span className="min-w-0 text-[14px] text-ink">{DISCREPANCY_KIND_LABEL[item.kind]}</span>
                      <span className="flex shrink-0 items-center gap-3 max-sm:flex-col max-sm:items-end max-sm:gap-1">
                        <Money value={item.amount} tone={item.direction === "SHORT" ? "short" : "excess"} />
                        <StatusChip kind="discrepancy" status={item.status} direction={item.direction} size="sm" />
                      </span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
          </div>
        </div>
      </div>

      {canSettle && <SettleDialog deposit={deposit} open={settling} onOpenChange={setSettling} />}
      {canSettle && <FailDialog deposit={deposit} open={failing} onOpenChange={setFailing} />}
    </>
  );
}

function SubmissionLine({ href, children }: { href?: string; children: ReactNode }) {
  const className = "flex items-center justify-between gap-3 px-5 py-3";
  return href ? (
    <Link href={href} className={cn(className, "transition-colors hover:bg-sunk/50")}>
      {children}
    </Link>
  ) : (
    <div className={className}>{children}</div>
  );
}

/** Reconciled → deposited → (fees) → settled, with the difference at each hop. */
function ReconciliationChain({ deposit }: { deposit: DepositDetail }) {
  const chain = deposit.reconciliation;
  const gateway = deposit.source === "GATEWAY";
  const failed = deposit.status === "FAILED";
  const steps: { label: string; amount: string | null; note?: ReactNode; tone: string; outcome?: ReactNode }[] = [
    { label: gateway ? "Captured UPI" : "Counted at branch", amount: chain.reconciled_amount, tone: gateway ? "bg-st-upi" : "bg-st-received" },
    {
      label: gateway ? "Gross settled" : "Deposited",
      amount: chain.deposited_amount,
      note: !isZero(chain.deposit_difference) && <Diff value={chain.deposit_difference} />,
      tone: "bg-st-deposited",
    },
    ...(gateway || !isZero(chain.fee_amount) || !isZero(chain.tax_amount)
      ? [
          {
            label: "After fees & tax",
            amount: chain.expected_settlement_amount,
            note: (
              <span className="text-[12px] text-faint">
                fee <Money value={chain.fee_amount} /> · tax <Money value={chain.tax_amount} />
              </span>
            ),
            tone: "bg-st-deposited",
          },
        ]
      : []),
    failed
      ? {
          label: "Returned by bank",
          amount: null,
          outcome: <span className="text-st-rejected-fg">Not credited</span>,
          note: deposit.failed_at && <span className="text-[12px] text-faint">{formatDate(deposit.failed_at)}</span>,
          tone: "bg-st-rejected",
        }
      : {
          label: "Settled in account",
          amount: chain.settled_amount,
          note: chain.settlement_difference && !isZero(chain.settlement_difference) && <Diff value={chain.settlement_difference} />,
          tone: "bg-st-settled",
        },
  ];

  return (
    <section aria-label="Reconciliation" className="overflow-hidden rounded-xl border border-rule bg-raised">
      <ol className={cn("grid divide-rule max-md:divide-y md:divide-x", steps.length === 4 ? "md:grid-cols-4" : "md:grid-cols-3")}>
        {steps.map((step) => (
          <li
            key={step.label}
            className="flex flex-col gap-1.5 px-5 py-4.5 max-md:grid max-md:grid-cols-[auto_minmax(0,1fr)] max-md:items-baseline max-md:gap-x-4 max-md:gap-y-1 max-md:py-3.5"
          >
            <span className="flex items-center gap-2 max-md:col-start-1 max-md:row-start-1">
              <span aria-hidden className={cn("size-1.5 rounded-full max-md:size-2", step.amount || step.outcome ? step.tone : "bg-rule-strong")} />
              <span className="eyebrow">{step.label}</span>
            </span>
            {step.amount ? (
              <Money
                value={step.amount}
                quietSymbol
                className="text-[22px] font-medium tracking-[-0.02em] text-ink max-md:col-start-2 max-md:row-start-1 max-md:text-right max-md:text-[18px]"
              />
            ) : (
              <span className="text-[15px] text-faint max-md:col-start-2 max-md:row-start-1 max-md:text-right max-md:text-[13.5px]">
                {step.outcome ?? "Awaiting statement"}
              </span>
            )}
            {step.note && <span className="max-md:col-start-2 max-md:text-right">{step.note}</span>}
          </li>
        ))}
      </ol>
      {chain.total_difference && (
        <p className="border-t border-rule bg-sunk/60 px-5 py-3 text-[13px] text-dim">
          {isZero(chain.total_difference) ? (
            <span className="text-st-settled-fg">
              {gateway
                ? "Reconciled end to end. Every captured payment reached the settlement account, net of fees and tax."
                : "Reconciled end to end. Every rupee counted at the branch reached the account."}
            </span>
          ) : (
            <>
              End to end difference <Diff value={chain.total_difference} />
            </>
          )}
        </p>
      )}
    </section>
  );
}

/** API differences are positive when money is short; shown as a signed change. */
function Diff({ value }: { value: string }) {
  return <Money value={negateMoney(value)} signed tone="direction" className="text-[12.5px]" />;
}

/** Why a bank credit can differ from the deposit; the cash-count reasons don't apply here. */
const SETTLEMENT_REASONS = ["BANK_CHARGES", "BANK_ERROR", "OTHER"] as const satisfies readonly DiscrepancyReasonCode[];
type SettlementReason = (typeof SETTLEMENT_REASONS)[number];

function SettleDialog({ deposit, open, onOpenChange }: { deposit: DepositDetail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const expected = deposit.reconciliation.expected_settlement_amount;
  const [amount, setAmount] = useState<string | null>(null);
  const [date, setDate] = useState(todayIST());
  const [reference, setReference] = useState("");
  const [remarks, setRemarks] = useState("");
  const [reason, setReason] = useState<SettlementReason | "">("");
  const settle = useSettleDeposit({ successMessage: (result) => `${result.deposit_number} settled` });

  const raw = amount ?? expected;
  const parsed = parseMoneyInput(raw);
  const mismatch = parsed !== null && compareMoney(parsed, expected) !== 0;
  const ready = parsed !== null && reference.trim().length >= 4 && (!mismatch || (reason !== "" && remarks.trim().length >= 5));

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Confirm settlement"
      description="Enter the credit exactly as it appears on the bank statement."
      footer={
        <Button
          disabled={!ready || settle.isPending}
          onClick={() =>
            parsed &&
            settle.mutate(
              {
                id: deposit.id,
                settled_amount: parsed,
                settled_on: date,
                settlement_reference: reference.trim(),
                remarks: remarks.trim() || undefined,
                reason_code: mismatch && reason ? reason : undefined,
              },
              { onSuccess: () => onOpenChange(false) },
            )
          }
        >
          {settle.isPending && <Loader2 className="animate-spin" />}
          {mismatch ? "Settle with mismatch" : "Confirm settlement"}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-lg bg-sunk px-4 py-3 text-[13.5px]">
          <span className="text-dim">Expected credit</span>
          <Money value={expected} className="font-medium text-ink" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2 sm:gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settled">Credited amount</Label>
            <MoneyInput id="settled" value={raw} onValueChange={setAmount} invalid={parsed === null} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="settled-on">Credited on</Label>
            <Input id="settled-on" type="date" value={date} max={todayIST()} min={deposit.deposit_date} onChange={(event) => setDate(event.target.value)} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="statement-ref">Statement reference</Label>
          <Input id="statement-ref" value={reference} onChange={(event) => setReference(event.target.value)} className="font-mono" placeholder="e.g. NEFT/HDFC/88213" />
        </div>
        {mismatch && (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="settle-reason">Reason for the difference</Label>
              <Select value={reason} onValueChange={(value) => setReason(value as SettlementReason)}>
                <SelectTrigger id="settle-reason" className="w-full">
                  <SelectValue placeholder="Choose a reason" />
                </SelectTrigger>
                <SelectContent>
                  {SETTLEMENT_REASONS.map((code) => (
                    <SelectItem key={code} value={code}>
                      {DISCREPANCY_REASON_LABEL[code]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="settle-remarks">Details</Label>
              <Textarea id="settle-remarks" rows={3} value={remarks} onChange={(event) => setRemarks(event.target.value)} placeholder="e.g. Bank deducted cash handling charges." />
              <p className="text-[12.5px] text-dim">A settlement mismatch is raised for the difference.</p>
            </div>
          </>
        )}
        <p className="text-[12.5px] text-dim">Deposited {formatDateTime(deposit.created_at)} by {deposit.created_by_name}.</p>
      </div>
    </ResponsiveDialog>
  );
}

function FailDialog({ deposit, open, onOpenChange }: { deposit: DepositDetail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [reason, setReason] = useState("");
  const fail = useFailDeposit();
  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Mark this deposit failed?"
      description="Use it when the bank returned the deposit. The cash goes back to the branch to be deposited again; this record is kept."
      footer={
        <Button
          variant="destructive-solid"
          disabled={reason.trim().length < 5 || fail.isPending}
          onClick={() => fail.mutate({ id: deposit.id, reason: reason.trim() }, { onSuccess: () => onOpenChange(false) })}
        >
          {fail.isPending && <Loader2 className="animate-spin" />}
          Mark failed
        </Button>
      }
    >
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="fail-reason">What the bank said</Label>
        <Textarea id="fail-reason" rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="e.g. Slip rejected: account number mismatch." />
      </div>
    </ResponsiveDialog>
  );
}
