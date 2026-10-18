"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryState } from "nuqs";
import { useCallback } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { DetailSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { paymentQueries } from "@/features/gateway/api";
import type { CollectionDetail } from "@/types/domain";

import { GATEWAY_NAME, PaymentConfirmation } from "./upi-payment-sheet";

/**
 * Where the gateway sends the customer back when its checkout could not open as a pop-up
 * (in-app browsers). Confirms the payment exactly as the pop-up flow does.
 */
export function UpiReturn() {
  const router = useRouter();
  const [orderId] = useQueryState("order_id");
  const orders = useQuery({
    ...paymentQueries.orders({ search: orderId ?? "", page_size: 5 }),
    enabled: Boolean(orderId),
  });
  const order = orders.data?.results.find((candidate) => candidate.provider_order_id === orderId);

  const toReceipt = useCallback(
    (receipt: CollectionDetail) => router.replace(`/app/agent/receipts/${receipt.id}?new=1`),
    [router],
  );
  const toLoan = useCallback(() => order && router.replace(`/app/agent/collect?loan=${order.loan}`), [order, router]);

  return (
    <div className="mx-auto w-full max-w-[560px]">
      <PageHeader eyebrow="UPI payment" title="Confirming payment" description="Checking with the gateway whether the customer paid." />
      {!orderId ? (
        <EmptyState
          bordered
          title="No payment to confirm"
          description="This page opens when a customer returns from the payment page."
          action={
            <Button asChild variant="outline">
              <Link href="/app/agent/collect">Collect a payment</Link>
            </Button>
          }
        />
      ) : orders.isPending ? (
        <DetailSkeleton />
      ) : orders.isError ? (
        <ErrorState error={orders.error} onRetry={() => void orders.refetch()} bordered />
      ) : !order ? (
        <EmptyState
          bordered
          title="Payment request not found"
          description={`No UPI request ${orderId} was raised from your account.`}
          action={
            <Button asChild variant="outline">
              <Link href="/app/agent/collect">Collect a payment</Link>
            </Button>
          }
        />
      ) : (
        <PaymentConfirmation
          order={order}
          gateway={GATEWAY_NAME[order.provider]}
          onPaid={toReceipt}
          onClose={toLoan}
          onRetry={toLoan}
        />
      )}
    </div>
  );
}
