"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { Money } from "@/components/money/money";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { customerQueries } from "@/features/customers/api";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { formatDayMonth, todayIST } from "@/lib/dates";
import type { Customer, ID, LoanSummary } from "@/types/domain";

/** Step one of Collect: find the customer, then the loan (skipped when there is only one). */
export function LoanPicker({ onPick }: { onPick: (loanId: ID) => void }) {
  const [draft, setDraft] = useState("");
  const search = useDebouncedValue(draft, 250);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const customers = useQuery(customerQueries.agentRoute({ search: search || undefined, page_size: 30 }));
  const detail = useQuery({ ...customerQueries.detail(customer?.id ?? 0), enabled: customer !== null });
  const loans = detail.data?.loans.filter((loan) => loan.status === "ACTIVE");
  const only = loans?.length === 1 ? loans[0].id : null;

  useEffect(() => {
    if (only !== null) onPick(only);
  }, [only, onPick]);

  if (customer) {
    if (detail.isPending || only !== null) return <CardListSkeleton count={2} />;
    if (detail.isError) return <ErrorState error={detail.error} onRetry={() => void detail.refetch()} compact bordered />;
    return (
      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={() => setCustomer(null)}
          className="-ml-1 flex min-h-11 w-fit items-center gap-1 text-[13.5px] text-dim transition-colors hover:text-ink sm:min-h-0"
        >
          <ChevronLeft aria-hidden className="size-4" />
          {customer.full_name}
        </button>
        {!loans?.length ? (
          <EmptyState bordered compact title="No active loans." description="Every loan for this customer is closed." />
        ) : (
          <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
            {loans.map((loan) => (
              <li key={loan.id}>
                <LoanOption loan={loan} onPick={onPick} />
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-1">
        <Input
          type="search"
          inputMode="search"
          autoFocus
          aria-label="Find a customer"
          placeholder="Name, phone or code"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="h-11 flex-1 text-base sm:text-[14px]"
        />
        <Button asChild variant="ghost" className="-mr-2 h-11 px-3 text-[15px] text-ink md:hidden">
          <Link href="/app/agent">Cancel</Link>
        </Button>
      </div>
      {customers.isPending ? (
        <CardListSkeleton count={5} />
      ) : customers.isError ? (
        <ErrorState error={customers.error} onRetry={() => void customers.refetch()} compact bordered />
      ) : customers.data.results.length === 0 ? (
        <EmptyState bordered compact title="No match." description="Only customers assigned to you appear here." />
      ) : (
        <ul className="rows-enter divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
          {customers.data.results.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => setCustomer(item)}
                className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-sunk/60 focus-visible:bg-sunk focus-visible:outline-none"
              >
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="truncate text-[14.5px] text-ink">{item.full_name}</span>
                  <span className="font-mono text-[11.5px] text-faint">{item.customer_code}</span>
                </span>
                <span className="flex items-center gap-2">
                  <Money value={item.outstanding} whole className="text-[13px] text-dim" />
                  <ChevronRight aria-hidden className="size-4 text-faint" />
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LoanOption({ loan, onPick }: { loan: LoanSummary; onPick: (id: ID) => void }) {
  const today = todayIST();
  return (
    <button
      type="button"
      onClick={() => onPick(loan.id)}
      className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left transition-colors hover:bg-sunk/60"
    >
      <span className="flex flex-col gap-0.5">
        <span className="font-mono text-[13px] text-ink">{loan.loan_number}</span>
        <span className="text-[12px] text-faint">
          EMI <Money value={loan.emi_amount} />
          {loan.next_due_date &&
            ` · ${loan.next_due_date === today ? "due today" : `${loan.next_due_date < today ? "due" : "next"} ${formatDayMonth(loan.next_due_date)}`}`}
        </span>
      </span>
      <Money value={loan.outstanding} whole className="text-[13px] text-dim" />
    </button>
  );
}
