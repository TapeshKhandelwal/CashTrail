"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Money } from "@/components/money/money";
import { Skeleton } from "@/components/ui/skeleton";
import { depositQueries } from "@/features/deposits/api";
import { discrepancyQueries } from "@/features/discrepancies/api";
import { gatewaySettlementQueries } from "@/features/gateway/api";
import { submissionQueries } from "@/features/submissions/api";
import { countOf } from "@/lib/format";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { ID } from "@/types/domain";

export type ActionDesk = "branch" | "finance" | "admin";

interface Action {
  key: string;
  tone: StatusTone;
  title: ReactNode;
  detail: string;
  href: string;
  done: boolean;
}

/** The handful of things waiting on this person right now, each a link to where it gets done. */
export function ActionStrip({ desk, branch }: { desk: ActionDesk; branch?: ID }) {
  const scope = branch ? { branch } : {};
  const branchDesk = desk !== "finance";
  const financeDesk = desk !== "branch";

  const toCount = useQuery({ ...submissionQueries.list({ ...scope, status: ["SUBMITTED"], page_size: 1 }), enabled: branchDesk });
  const toDeposit = useQuery({ ...depositQueries.pendingCash(scope), enabled: branchDesk });
  const toSettle = useQuery({ ...depositQueries.list({ ...scope, status: ["PENDING"], source: "CASH", page_size: 100 }), enabled: financeDesk });
  const upi = useQuery({ ...gatewaySettlementQueries.pending(), enabled: financeDesk });
  const open = useQuery(discrepancyQueries.list({ ...scope, status: ["OPEN"], page_size: 1 }));

  const queries = [open, ...(branchDesk ? [toCount, toDeposit] : []), ...(financeDesk ? [toSettle, upi] : [])];
  if (queries.some((query) => query.isPending)) {
    return (
      <div className="grid-ruled grid-cols-1 sm:grid-cols-3" aria-hidden>
        {[0, 1, 2].map((index) => (
          <div key={index} className="flex flex-col gap-2 px-5 py-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-4 w-40" />
          </div>
        ))}
      </div>
    );
  }

  const actions: Action[] = [];
  if (branchDesk) {
    const count = toCount.data?.count ?? 0;
    actions.push({
      key: "count",
      tone: "submitted",
      title: count ? countOf(count, "hand-over") + " to count" : "No hand-overs waiting",
      detail: count ? "Count the cash and accept or reject it." : "Agents' cash appears here when they hand it over.",
      href: "/app/branch/submissions?status=SUBMITTED",
      done: count === 0,
    });
    const cash = toDeposit.data;
    actions.push({
      key: "deposit",
      tone: "received",
      title: cash && cash.count ? <><Money value={cash.total_amount} whole /> to bank</> : "Nothing to deposit",
      detail: cash && cash.count ? `${countOf(cash.count, "counted hand-over")} waiting for a deposit slip.` : "Every counted rupee is in the bank.",
      href: "/app/branch/deposits/new",
      done: !cash?.count,
    });
  }
  if (financeDesk) {
    const pending = toSettle.data?.results ?? [];
    const late = pending.filter((deposit) => deposit.is_delayed).length;
    actions.push({
      key: "settle",
      tone: late ? "delayed" : "deposited",
      title: pending.length ? `${countOf(pending.length, "deposit")} to match` : "Statement matched",
      detail: pending.length ? (late ? `${late} past the 2-day settlement SLA.` : "Confirm each against the bank statement.") : "No deposit is waiting for the statement.",
      href: "/app/finance/settlements",
      done: pending.length === 0,
    });
    if (desk === "finance") {
      const unsettled = upi.data;
      actions.push({
        key: "upi",
        tone: "upi",
        title: unsettled && unsettled.count ? <><Money value={unsettled.total_amount} whole /> UPI to settle</> : "UPI settled",
        detail: unsettled && unsettled.count ? `${countOf(unsettled.count, "captured payment")} awaiting the gateway batch.` : "Every captured payment is settled.",
        href: "/app/finance/gateway",
        done: !unsettled?.count,
      });
    }
  }
  const openCount = open.data?.count ?? 0;
  actions.push({
    key: "discrepancies",
    tone: "short",
    title: openCount ? `${countOf(openCount, "discrepancy", "discrepancies")} open` : "No open discrepancies",
    detail: openCount ? "Recover or write off each, with a note." : "Every count and deposit reconciles.",
    href: desk === "branch" ? "/app/branch/discrepancies" : "/app/finance/discrepancies",
    done: openCount === 0,
  });

  return (
    <section aria-label="Needs you now" className="flex flex-col gap-3">
      <h2 className="eyebrow">Needs you now</h2>
      <ul className={cn("grid-ruled grid-cols-1 sm:grid-cols-2", actions.length === 3 ? "lg:grid-cols-3" : "lg:grid-cols-4")}>
        {actions.map((action) => (
          <li key={action.key}>
            <Link
              href={action.href}
              className={cn(
                "group flex h-full items-start justify-between gap-3 bg-raised px-5 py-4 transition-colors hover:bg-sunk/60",
                !action.done && cn("border-l-2", TONE_CLASSES[action.tone].border),
              )}
            >
              <span className="flex min-w-0 flex-col gap-1">
                <span className={cn("text-[14.5px] font-medium", action.done ? "text-dim" : "text-ink")}>{action.title}</span>
                <span className="text-[12.5px] leading-snug text-dim">{action.detail}</span>
              </span>
              {action.done ? (
                <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-st-settled-fg" />
              ) : (
                <ArrowRight aria-hidden className="mt-0.5 size-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5" />
              )}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
