"use client";

import { useQuery } from "@tanstack/react-query";
import { parseAsString, useQueryState } from "nuqs";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { Input } from "@/components/ui/input";
import { customerQueries } from "@/features/customers/api";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { countOf, formatCount } from "@/lib/format";

import { CustomerRow } from "./customer-row";

export function AgentCustomers() {
  const [search, setSearch] = useQueryState("q", parseAsString.withDefault("").withOptions({ history: "replace" }));
  const [draft, setDraft] = useState(search);
  const term = useDebouncedValue(draft, 250);
  useEffect(() => {
    void setSearch(term || null);
  }, [term, setSearch]);

  const customers = useQuery(customerQueries.agentRoute({ search: search || undefined, page_size: 100 }));

  return (
    <div className="mx-auto w-full max-w-[760px]">
      <PageHeader
        eyebrow={
          !customers.data
            ? "Assigned to you"
            : search
              ? countOf(customers.data.count, "match", "matches")
              : `${formatCount(customers.data.count)} assigned`
        }
        title="Customers"
        description="Everyone on your route, most urgent first."
      />
      <div className="flex flex-col gap-3">
        <Input
          type="search"
          inputMode="search"
          aria-label="Search customers"
          placeholder="Name, phone or customer code"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="h-11 text-base sm:text-[14px]"
        />
        {customers.isPending ? (
          <CardListSkeleton count={6} />
        ) : customers.isError ? (
          <ErrorState error={customers.error} onRetry={() => void customers.refetch()} bordered compact />
        ) : customers.data.results.length === 0 ? (
          <EmptyState bordered compact title={search ? "No match." : "No customers assigned yet."} />
        ) : (
          <ul className="rows-enter divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
            {customers.data.results.map((customer) => (
              <li key={customer.id}>
                <CustomerRow customer={customer} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
