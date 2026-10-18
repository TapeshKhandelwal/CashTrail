"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/feedback/empty-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { depositQueries } from "@/features/deposits/api";
import { discrepancyQueries } from "@/features/discrepancies/api";
import { formatDate, formatRelative } from "@/lib/dates";
import { DISCREPANCY_KIND_LABEL, type ID } from "@/types/domain";

export interface AttentionLinks {
  discrepancies: string;
  deposit: (id: ID) => string;
  deposits: string;
}

/** What needs a decision: open discrepancies and settlements past their SLA. */
export function AttentionPanel({ branch, links }: { branch?: ID; links: AttentionLinks }) {
  const scope = branch ? { branch } : {};
  const discrepancies = useQuery(discrepancyQueries.list({ ...scope, status: ["OPEN"], page_size: 4, ordering: "-amount" }));
  const delayed = useQuery(depositQueries.list({ ...scope, delayed: true, page_size: 4, ordering: "deposit_date" }));

  const loading = discrepancies.isPending || delayed.isPending;
  const items = [
    ...(discrepancies.data?.results ?? []).map((item) => ({
      key: `d-${item.id}`,
      href: links.discrepancies,
      title: DISCREPANCY_KIND_LABEL[item.kind],
      who: item.agent_name ?? item.branch_code,
      reference: item.submission_number ?? item.deposit_number,
      when: `raised ${formatRelative(item.created_at)}`,
      amount: <Money value={item.amount} tone={item.direction === "SHORT" ? "short" : "excess"} />,
    })),
    ...(delayed.data?.results ?? []).map((item) => ({
      key: `p-${item.id}`,
      href: links.deposit(item.id),
      title: "Settlement overdue",
      who: item.bank_account.bank_name,
      reference: item.deposit_number,
      when: `deposited ${formatDate(item.deposit_date)}`,
      amount: <Money value={item.deposited_amount} />,
    })),
  ];

  return (
    <SectionCard
      eyebrow="Needs attention"
      title="Open items"
      flush
      actions={
        <Link href={links.discrepancies} className="inline-flex items-center gap-1 text-[12.5px] text-dim hover:text-ink">
          All discrepancies
          <ArrowUpRight className="size-3.5" />
        </Link>
      }
    >
      {loading ? (
        <CardListSkeleton count={3} className="border-0 p-2" />
      ) : items.length === 0 ? (
        <EmptyState compact illustration="settled" title="Nothing open." description="Every count, deposit and settlement reconciles." />
      ) : (
        <ul className="rows-enter divide-y divide-rule">
          {items.map((item) => (
            <li key={item.key}>
              <Link
                href={item.href}
                className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-4 gap-y-1 px-5 py-3.5 transition-colors outline-none hover:bg-sunk/50 focus-visible:bg-sunk"
              >
                <span className="text-[13.5px] text-ink">{item.title}</span>
                <span className="text-right text-[13.5px] tabular-nums">{item.amount}</span>
                <span className="truncate text-[12.5px] text-dim">{item.who}</span>
                <span className="text-right text-[11.5px] whitespace-nowrap text-faint">{item.when}</span>
                {item.reference && <span className="col-span-2 truncate font-mono text-[11px] text-faint">{item.reference}</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
