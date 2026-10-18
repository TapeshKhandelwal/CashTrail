"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import Link from "next/link";

import { CustomerProfile } from "@/components/customers/customer-profile";
import { EmptyState } from "@/components/feedback/empty-state";
import { QueryView } from "@/components/feedback/query-view";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { LoanPanel } from "@/components/loans/loan-panel";
import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { customerQueries } from "@/features/customers/api";
import type { ID } from "@/types/domain";

export function AgentCustomer({ id }: { id: ID }) {
  const user = useSession();
  const customer = useQuery(customerQueries.detail(id));

  return (
    <QueryView query={customer} loading={<DetailSkeleton />} errorTitle="We couldn't load this customer.">
      {(data) => {
        const active = data.loans.filter((loan) => loan.status === "ACTIVE");
        return (
          <div className="mx-auto w-full max-w-[900px]">
            <PageCrumb label={data.full_name} />
            <PageHeader
              eyebrow="Customer"
              title={data.full_name}
              actions={
                active[0] && (
                  <Button asChild className="max-sm:h-11 max-sm:w-full">
                    <Link href={`/app/agent/collect?loan=${active[0].id}`}>
                      <Plus data-icon="inline-start" />
                      Collect
                    </Link>
                  </Button>
                )
              }
            />
            <div className="flex flex-col gap-5">
              <CustomerProfile customer={data} />
              {data.loans.length === 0 ? (
                <EmptyState bordered compact title="No loans yet." />
              ) : (
                data.loans.map((loan) => (
                  <LoanPanel
                    key={loan.id}
                    loan={loan}
                    // Agents open only their own receipts; earlier ones by another agent stay as plain rows.
                    receiptHref={(repayment) => (repayment.agent === user.id ? `/app/agent/receipts/${repayment.id}` : null)}
                    actions={
                      loan.status === "ACTIVE" &&
                      active.length > 1 && (
                        <Button asChild size="sm" variant="outline">
                          <Link href={`/app/agent/collect?loan=${loan.id}`}>Collect</Link>
                        </Button>
                      )
                    }
                  />
                ))
              )}
            </div>
          </div>
        );
      }}
    </QueryView>
  );
}
