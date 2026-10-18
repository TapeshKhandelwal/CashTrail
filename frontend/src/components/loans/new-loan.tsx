"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { parseAsInteger, useQueryState } from "nuqs";
import { useState } from "react";

import { ConfirmDialog, ConfirmFacts } from "@/components/feedback/confirm-dialog";
import { PageCrumb } from "@/components/layout/page-crumb";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { StickyActionBar } from "@/components/layout/sticky-action-bar";
import { Money } from "@/components/money/money";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { customerQueries } from "@/features/customers/api";
import { useCreateLoan } from "@/features/loans/api";
import { useBranchScope } from "@/hooks/use-branch-scope";

import { LoanTermFields, SchedulePreviewView, newLoanTerms, useLoanTermsDraft } from "./loan-terms";

export function NewLoan({ basePath }: { basePath: string }) {
  const router = useRouter();
  const { branch } = useBranchScope();
  const [customerId, setCustomerId] = useQueryState("customer", parseAsInteger);
  const customers = useQuery(customerQueries.list({ is_active: true, page_size: 100, ordering: "full_name", ...(branch ? { branch } : {}) }));
  const draft = useLoanTermsDraft(newLoanTerms());
  const [confirming, setConfirming] = useState(false);
  const create = useCreateLoan();

  const { parsedPrincipal, preview, rateValid } = draft;
  const { rate, tenure, disbursed } = draft.values;
  const customer = customers.data?.results.find((item) => item.id === customerId);
  const ready = customerId !== null && parsedPrincipal !== null && rateValid && draft.settled;

  const createButton = (size: "lg" | "xl") => (
    <Button size={size} disabled={!ready || create.isPending} onClick={() => setConfirming(true)}>
      {create.isPending && <Loader2 className="animate-spin" />}
      Create loan
    </Button>
  );

  return (
    <>
      <PageCrumb label="New loan" />
      <PageHeader
        eyebrow="Money · New loan"
        title="Create a loan"
        description="Monthly EMIs on a reducing balance. The schedule is fixed once the first repayment is recorded."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[400px_minmax(0,1fr)]">
        <SectionCard eyebrow="Terms" title="Borrower and terms" className="lg:sticky lg:top-24">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="customer">Customer</Label>
              <Select value={customerId ? String(customerId) : ""} onValueChange={(value) => void setCustomerId(Number(value))}>
                <SelectTrigger id="customer" className="w-full">
                  <SelectValue placeholder={customers.isPending ? "Loading…" : "Choose a customer"} />
                </SelectTrigger>
                <SelectContent>
                  {customers.data?.results.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.full_name} · {item.customer_code}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <LoanTermFields draft={draft} />
            <div className="flex flex-col max-md:hidden">{createButton("lg")}</div>
          </div>
        </SectionCard>

        <div className="@container flex min-w-0 flex-col gap-5">
          <SchedulePreviewView draft={draft} />
        </div>
      </div>

      <div className="md:hidden">
        <StickyActionBar>
          <div className="flex items-center justify-between gap-3 text-[13px]">
            <span className="min-w-0 truncate text-dim">{customer ? customer.full_name : "Choose a customer"}</span>
            <span className="shrink-0 text-dim tabular-nums">
              {preview.data ? (
                <>
                  EMI <Money value={preview.data.emi_amount} className="font-medium text-ink" /> × {tenure}
                </>
              ) : (
                "—"
              )}
            </span>
          </div>
          {createButton("xl")}
        </StickyActionBar>
      </div>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Create this loan?"
        description="The repayment schedule is generated now and the loan appears on the agent's route."
        confirmLabel="Create loan"
        loading={create.isPending}
        onConfirm={() =>
          customerId &&
          parsedPrincipal &&
          create.mutate(
            { customer_id: customerId, principal: parsedPrincipal, annual_interest_rate: rate, tenure_months: Number(tenure), disbursed_on: disbursed },
            { onSuccess: () => router.push(`${basePath}/customers/${customerId}`), onSettled: () => setConfirming(false) },
          )
        }
      >
        <ConfirmFacts
          rows={[
            ["Customer", customer?.full_name ?? "—"],
            ["Principal", <Money key="p" value={parsedPrincipal ?? "0.00"} />],
            ["EMI", <Money key="e" value={preview.data?.emi_amount ?? "0.00"} />],
            ["Tenure", `${tenure} months at ${rate}%`],
          ]}
        />
      </ConfirmDialog>
    </>
  );
}
