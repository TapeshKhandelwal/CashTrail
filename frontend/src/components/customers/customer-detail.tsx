"use client";

import { useQuery } from "@tanstack/react-query";
import { PencilLine, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { QueryView } from "@/components/feedback/query-view";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { EditLoanTerms } from "@/components/loans/edit-loan-terms";
import { LoanPanel } from "@/components/loans/loan-panel";
import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { customerQueries, useAssignCustomer, useUpdateCustomer } from "@/features/customers/api";
import { useAgentOptions } from "@/hooks/use-filter-options";
import { isZero } from "@/lib/money";
import type { CustomerDetail as Customer, ID } from "@/types/domain";

import { CustomerFormDialog } from "./customer-form-dialog";
import { CustomerProfile } from "./customer-profile";

export function CustomerDetail({ id, basePath }: { id: ID; basePath: string }) {
  const customer = useQuery(customerQueries.detail(id));
  return (
    <QueryView query={customer} loading={<DetailSkeleton />} errorTitle="We couldn't load this customer.">
      {(data) => <Body customer={data} basePath={basePath} />}
    </QueryView>
  );
}

function Body({ customer, basePath }: { customer: Customer; basePath: string }) {
  const user = useSession();
  const canWrite = user.role === "ADMIN" || user.role === "BRANCH_MANAGER";

  return (
    <>
      <PageCrumb label={customer.full_name} />
      <PageHeader
        eyebrow={`${customer.branch_code} · Customer`}
        title={customer.full_name}
        actions={
          canWrite &&
          customer.is_active && (
            <Button asChild>
              <Link href={`${basePath}/loans/new?customer=${customer.id}`}>
                <Plus data-icon="inline-start" />
                New loan
              </Link>
            </Button>
          )
        }
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-5">
          <CustomerProfile customer={customer} />
          {customer.loans.length === 0 ? (
            <EmptyState bordered compact title="No loans yet." description="Create one to generate the repayment schedule." />
          ) : (
            customer.loans.map((loan) => (
              <LoanPanel
                key={loan.id}
                loan={loan}
                receiptHref={(repayment) => `${basePath}/collections/${repayment.id}`}
                // Only a loan with nothing paid can still have unlocked terms; the action checks the rest.
                actions={canWrite && loan.status === "ACTIVE" && isZero(loan.amount_paid) && <EditLoanTerms loanId={loan.id} />}
              />
            ))
          )}
        </div>
        {canWrite && <ManagePanel customer={customer} />}
      </div>
    </>
  );
}

function ManagePanel({ customer }: { customer: Customer }) {
  const agents = useAgentOptions(customer.branch);
  const assign = useAssignCustomer();
  const update = useUpdateCustomer({ successMessage: (result) => (result.is_active ? "Customer reactivated" : "Customer deactivated") });
  const [editing, setEditing] = useState(false);

  return (
    <SectionCard
      eyebrow="Manage"
      title="Details, visits and status"
      className="lg:sticky lg:top-24"
      actions={
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          <PencilLine data-icon="inline-start" />
          Edit details
        </Button>
      }
    >
      <CustomerFormDialog open={editing} onOpenChange={setEditing} customer={customer} />
      <div className="flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] text-ink">Visiting agent</span>
          <Select
            value={customer.assigned_agent ? String(customer.assigned_agent) : "none"}
            disabled={assign.isPending}
            onValueChange={(value) => assign.mutate({ id: customer.id, agentId: value === "none" ? null : Number(value) })}
          >
            <SelectTrigger className="w-full" aria-label="Visiting agent">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Unassigned</SelectItem>
              {agents.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-[12.5px] text-dim">Only the assigned agent can collect from this customer.</p>
        </div>
        <label className="flex items-start justify-between gap-4 border-t border-rule pt-4">
          <span className="flex flex-col gap-0.5">
            <span className="text-[13px] text-ink">Active</span>
            <span className="text-[12.5px] text-dim">A customer with an active loan cannot be deactivated.</span>
          </span>
          <Switch
            checked={customer.is_active}
            disabled={update.isPending}
            onCheckedChange={(checked) => update.mutate({ id: customer.id, is_active: checked })}
          />
        </label>
      </div>
    </SectionCard>
  );
}
