"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { ConfirmDialog, ConfirmFacts } from "@/components/feedback/confirm-dialog";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { MoneyInput } from "@/components/money/money-input";
import { VarianceMeter } from "@/components/money/variance-meter";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { bankAccountQueries, depositQueries, useCreateDeposit } from "@/features/deposits/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { ApiError } from "@/lib/api/errors";
import { formatDateTime, formatDayMonth, formatTime, todayIST } from "@/lib/dates";
import { countOf, formatCount } from "@/lib/format";
import { compareMoney, isZero, parseMoneyInput, sumMoney } from "@/lib/money";
import type { ID, PendingCashSubmission } from "@/types/domain";

export function NewDeposit() {
  const { branch, canSwitch, setBranch } = useBranchScope();
  const pending = useQuery(depositQueries.pendingCash(branch ? { branch } : {}));
  const accounts = useQuery(bankAccountQueries.list({ is_active: true, is_gateway: false, page_size: 50 }));
  // A slip carries one branch's cash, so a user who sees every branch picks one first.
  const branches = useMemo(() => pendingByBranch(pending.data?.submissions ?? []), [pending.data]);

  return (
    <>
      <PageCrumb label="New deposit" />
      <PageHeader
        eyebrow="Money · New deposit"
        title="Deposit counted cash"
        description="Choose the accepted hand-overs on this slip, then record the bank's reference exactly as printed."
        actions={
          canSwitch &&
          branch && (
            <Button variant="outline" onClick={() => setBranch(null)}>
              Change branch
            </Button>
          )
        }
      />
      {pending.isPending || accounts.isPending ? (
        <DetailSkeleton />
      ) : pending.isError ? (
        <ErrorState error={pending.error} onRetry={() => void pending.refetch()} bordered />
      ) : accounts.isError ? (
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} bordered />
      ) : pending.data.submissions.length === 0 ? (
        <EmptyState
          bordered
          illustration="settled"
          title="No counted cash to deposit."
          description="Accepted hand-overs appear here until they are banked."
          action={
            <Button asChild variant="outline">
              <Link href="/app/branch/submissions">Go to submissions</Link>
            </Button>
          }
        />
      ) : branches.length > 1 ? (
        <BranchChoice branches={branches} onChoose={setBranch} />
      ) : (
        <DepositForm key={branches[0]?.id} submissions={pending.data.submissions} accounts={accounts.data.results} showBranch={canSwitch && !branch} />
      )}
    </>
  );
}

interface BranchCash {
  id: ID;
  code: string;
  count: number;
  total: string;
}

function pendingByBranch(submissions: PendingCashSubmission[]): BranchCash[] {
  const byBranch = new Map<ID, PendingCashSubmission[]>();
  for (const item of submissions) byBranch.set(item.branch, [...(byBranch.get(item.branch) ?? []), item]);
  return Array.from(byBranch, ([id, items]) => ({
    id,
    code: items[0]!.branch_code,
    count: items.length,
    total: sumMoney(items.map((item) => item.received_amount ?? item.expected_amount)),
  })).sort((a, b) => a.code.localeCompare(b.code));
}

function BranchChoice({ branches, onChoose }: { branches: BranchCash[]; onChoose: (branch: ID) => void }) {
  return (
    <SectionCard flush eyebrow={`${countOf(branches.length, "branch", "branches")} with counted cash`} title="Which branch is depositing?" description="A deposit slip carries one branch's cash. Pick the branch to see its counted hand-overs.">
      <ul className="divide-y divide-rule">
        {branches.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onChoose(item.id)}
              className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left transition-colors outline-none hover:bg-sunk/50 focus-visible:bg-sunk/60"
            >
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="font-mono text-[14px] text-ink">{item.code}</span>
                <span className="text-[12.5px] text-dim">{countOf(item.count, "hand-over")} counted</span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <Money value={item.total} className="text-ink" />
                <ChevronRight aria-hidden className="size-4 text-faint" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function DepositForm({
  submissions,
  accounts,
  showBranch,
}: {
  submissions: PendingCashSubmission[];
  accounts: { id: ID; bank_name: string; account_name: string; masked_account_number: string }[];
  /** For users who see every branch: which branch the cash is from. */
  showBranch: boolean;
}) {
  const router = useRouter();
  const [excluded, setExcluded] = useState<Set<ID>>(new Set());
  const [account, setAccount] = useState<string>(accounts[0] ? String(accounts[0].id) : "");
  const [date, setDate] = useState(todayIST());
  const [reference, setReference] = useState("");
  const [amount, setAmount] = useState<string | null>(null);
  const [remarks, setRemarks] = useState("");
  const [confirming, setConfirming] = useState(false);
  // Navigate from the hook: once the last pending hand-over is banked this form unmounts.
  const create = useCreateDeposit({
    successMessage: (deposit) => `${deposit.deposit_number} recorded`,
    onSuccess: (deposit) => router.push(`/app/branch/deposits/${deposit.id}`),
  });

  const selected = useMemo(() => submissions.filter((item) => !excluded.has(item.id)), [submissions, excluded]);
  const expected = sumMoney(selected.map((item) => item.received_amount ?? item.expected_amount));
  const raw = amount ?? expected;
  const deposited = parseMoneyInput(raw);
  const mismatch = deposited !== null && compareMoney(deposited, expected) !== 0;
  const duplicate = create.error instanceof ApiError && create.error.is("DUPLICATE_BANK_REFERENCE");
  // The server refuses a slip that mixes branches; the branch step means this always holds.
  const singleBranch = new Set(selected.map((item) => item.branch)).size === 1;
  const ready =
    selected.length > 0 &&
    singleBranch &&
    account !== "" &&
    reference.trim().length >= 4 &&
    deposited !== null &&
    !isZero(deposited) &&
    (!mismatch || remarks.trim().length >= 5);

  const toggle = (id: ID) =>
    setExcluded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <form
      className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]"
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) setConfirming(true);
      }}
    >
      <SectionCard
        flush
        eyebrow={`${formatCount(selected.length)} of ${formatCount(submissions.length)} hand-overs`}
        title="Cash on this slip"
        footer={
          <div className="flex items-center justify-between text-[13.5px]">
            <span className="text-dim">Counted total</span>
            <Money value={expected} className="font-medium text-ink" />
          </div>
        }
      >
        <ul className="divide-y divide-rule">
          {submissions.map((item) => (
            <li key={item.id}>
              <label className="flex cursor-pointer items-center gap-3.5 px-5 py-3.5 transition-colors hover:bg-sunk/50">
                <Checkbox checked={!excluded.has(item.id)} onCheckedChange={() => toggle(item.id)} aria-label={item.submission_number} />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-[14px] text-ink">{item.agent_name}</span>
                  <span className="font-mono text-[11.5px] text-faint lg:truncate">
                    {showBranch && <span className="text-dim">{item.branch_code} · </span>}
                    <span className="wrap-anywhere">{item.submission_number}</span>
                    {item.reviewed_at && (
                      <>
                        <span className="max-lg:hidden"> · counted {formatDateTime(item.reviewed_at)}</span>
                        <span className="block lg:hidden">
                          {formatDayMonth(item.reviewed_at)}, {formatTime(item.reviewed_at)}
                        </span>
                      </>
                    )}
                  </span>
                </span>
                <Money value={item.received_amount ?? item.expected_amount} className="text-ink" />
              </label>
            </li>
          ))}
        </ul>
      </SectionCard>

      <div className="flex flex-col gap-5 lg:sticky lg:top-24">
        <SectionCard eyebrow="Deposit slip" title="As printed by the bank">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="account">Company account</Label>
              <Select value={account} onValueChange={setAccount}>
                <SelectTrigger id="account" className="w-full">
                  <SelectValue placeholder="Choose the account" />
                </SelectTrigger>
                <SelectContent>
                  {accounts.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.bank_name} · {item.masked_account_number}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 sm:gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="date">Deposit date</Label>
                <Input id="date" type="date" value={date} max={todayIST()} onChange={(event) => setDate(event.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="amount">Amount on slip</Label>
                <MoneyInput id="amount" value={raw} onValueChange={setAmount} invalid={deposited === null} />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reference">Slip / transaction reference</Label>
              <Input
                id="reference"
                value={reference}
                onChange={(event) => {
                  setReference(event.target.value);
                  if (duplicate) create.reset();
                }}
                aria-invalid={duplicate || undefined}
                placeholder="e.g. HDFC261017218378"
                className="font-mono uppercase placeholder:normal-case"
              />
              {duplicate && (
                <p role="alert" className="text-[12.5px] text-st-rejected-fg">
                  This reference is already recorded against another deposit for this account. Check the slip; every bank
                  reference can be used once.
                </p>
              )}
            </div>
          </div>
        </SectionCard>

        {deposited && mismatch && (
          <>
            <VarianceMeter expected={expected} counted={deposited} expectedLabel="Counted" countedLabel="On slip" />
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="remarks">Why the slip differs from the count</Label>
              <Textarea
                id="remarks"
                rows={3}
                placeholder="e.g. One ₹500 note refused by the bank as counterfeit."
                value={remarks}
                onChange={(event) => setRemarks(event.target.value)}
              />
              <p className="text-[12.5px] text-dim">A deposit mismatch is raised for finance to review.</p>
            </div>
          </>
        )}

        <Button type="submit" size="xl" disabled={!ready || create.isPending}>
          {create.isPending && <Loader2 className="animate-spin" />}
          <span>Record deposit {deposited && !isZero(deposited) && <Money value={deposited} />}</span>
        </Button>
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Record this deposit?"
        description="The cash leaves the branch's books and waits for finance to match it to the bank statement."
        confirmLabel="Record deposit"
        loading={create.isPending}
        onConfirm={() =>
          deposited &&
          create.mutate(
            {
              submission_ids: selected.map((item) => item.id),
              bank_account_id: Number(account),
              deposited_amount: deposited,
              deposit_date: date,
              reference_number: reference.trim(),
              remarks: remarks.trim() || undefined,
            },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <ConfirmFacts
          rows={[
            ["Hand-overs", formatCount(selected.length)],
            ["Counted", <Money key="c" value={expected} />],
            ["On slip", <Money key="d" value={deposited ?? "0.00"} />],
            ["Reference", <span key="r" className="font-mono">{reference.trim().toUpperCase()}</span>],
          ]}
        />
      </ConfirmDialog>
    </form>
  );
}
