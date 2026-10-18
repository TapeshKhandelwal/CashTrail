"use client";

import { useQuery } from "@tanstack/react-query";
import { Plus, Printer, Share2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";

import { QueryView } from "@/components/feedback/query-view";
import { SuccessCheck } from "@/components/feedback/success-check";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageCrumb } from "@/components/layout/page-crumb";
import { ReceiptCard } from "@/components/receipt/receipt-card";
import { Button } from "@/components/ui/button";
import { collectionQueries } from "@/features/collections/api";
import { formatDateTime } from "@/lib/dates";
import { formatINR } from "@/lib/format";
import type { CollectionDetail, ID } from "@/types/domain";

function shareText(receipt: CollectionDetail): string {
  const lines = [
    `CashTrail receipt ${receipt.receipt_number}`,
    `${formatINR(receipt.amount)} received from ${receipt.customer_name} for loan ${receipt.loan_number}`,
    `${formatDateTime(receipt.collected_at)} IST`,
  ];
  if (receipt.status === "VOIDED") {
    lines.push("This receipt was voided.");
  } else if (receipt.balance_after !== null) {
    lines.push(`Balance after this payment: ${formatINR(receipt.balance_after)}`);
  }
  return lines.join("\n");
}

async function share(receipt: CollectionDetail) {
  const text = shareText(receipt);
  if (navigator.share) {
    await navigator.share({ title: receipt.receipt_number, text }).catch(() => undefined);
    return;
  }
  await navigator.clipboard.writeText(text);
  toast.success("Receipt copied");
}

export function ReceiptView({ id, newHref = "/app/agent/collect" }: { id: ID; newHref?: string }) {
  const receipt = useQuery(collectionQueries.detail(id));
  const isNew = useSearchParams().get("new") === "1";

  return (
    <QueryView query={receipt} loading={<DetailSkeleton />} errorTitle="We couldn't load this receipt.">
      {(data) => (
        <div className="mx-auto flex w-full max-w-[560px] flex-col gap-6">
          <PageCrumb label={data.receipt_number} />
          {isNew && (
            <div role="status" className="flex items-center gap-3 animate-rise">
              <SuccessCheck />
              <div className="flex flex-col">
                <p className="title-section">{data.mode === "UPI" ? "Payment confirmed." : "Receipt recorded."}</p>
                <p className="text-[13px] text-dim">
                  {data.mode === "UPI" ? "The gateway confirmed it; nothing to hand over." : "Hand the cash over at the branch today."}
                </p>
              </div>
            </div>
          )}
          <ReceiptCard
            receipt={data}
            arriving={isNew}
            actions={
              <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:justify-center">
                <Button variant="outline" className="max-sm:h-11" onClick={() => window.print()}>
                  <Printer data-icon="inline-start" />
                  Print
                </Button>
                <Button variant="outline" className="max-sm:h-11" onClick={() => void share(data)}>
                  <Share2 data-icon="inline-start" />
                  Share
                </Button>
                {isNew && (
                  <Button asChild className="max-sm:order-first max-sm:col-span-2 max-sm:h-12 max-sm:rounded-xl max-sm:text-[15px]">
                    <Link href={newHref}>
                      <Plus data-icon="inline-start" />
                      Next collection
                    </Link>
                  </Button>
                )}
              </div>
            }
          />
        </div>
      )}
    </QueryView>
  );
}
