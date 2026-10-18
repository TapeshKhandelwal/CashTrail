"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RotateCcw, Smartphone } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useEffect, useRef, useState } from "react";

import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Money } from "@/components/money/money";
import { Button } from "@/components/ui/button";
import { paymentQueries, useMockPay, useVerifyPayment } from "@/features/gateway/api";
import { ApiError } from "@/lib/api/errors";
import { MONEY_KEYS } from "@/lib/api/query-keys";
import type { CheckoutOptions, CollectionDetail, GatewayOrder, OrderCreated, PaymentResult } from "@/types/domain";

interface RazorpayResponse {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayInstance {
  open: () => void;
  on: (event: "payment.failed", handler: () => void) => void;
}

interface CashfreeCheckoutResult {
  error?: { message?: string };
  redirect?: boolean;
  paymentDetails?: { paymentMessage?: string };
}

interface CashfreeInstance {
  checkout: (options: { paymentSessionId: string; redirectTarget: "_modal" }) => Promise<CashfreeCheckoutResult>;
}

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance;
    Cashfree?: (options: { mode: "sandbox" | "production" }) => CashfreeInstance;
  }
}

function loadScript(src: string): Promise<void> {
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${src}"]`);
  if (existing?.dataset.loaded) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const script = existing ?? Object.assign(document.createElement("script"), { src, async: true });
    script.addEventListener("load", () => {
      script.dataset.loaded = "true";
      resolve();
    });
    script.addEventListener("error", () => {
      // A failed tag never loads again; drop it so the next attempt starts a fresh download.
      script.remove();
      reject(new Error("Checkout failed to load"));
    });
    if (!existing) document.head.append(script);
  });
}

export const GATEWAY_NAME: Record<CheckoutOptions["provider"], string> = {
  RAZORPAY: "Razorpay",
  CASHFREE: "Cashfree",
  MOCK: "the gateway",
};

interface UpiPaymentSheetProps {
  created: OrderCreated | null;
  onClose: () => void;
  onPaid: (receipt: CollectionDetail) => void;
}

/**
 * The customer pays on their own phone. Cashfree and Razorpay run their own checkout; the
 * mock gateway (demo and tests) shows a UPI QR and lets the agent play the customer's side.
 * Either way the receipt is issued only once the server has the gateway's word for it.
 */
export function UpiPaymentSheet({ created, onClose, onPaid }: UpiPaymentSheetProps) {
  if (!created) return null;
  const props = { created, onClose, onPaid };
  switch (created.checkout.provider) {
    case "CASHFREE":
      return <CashfreeCheckout key={created.order.id} {...props} />;
    case "RAZORPAY":
      return <RazorpayCheckout key={created.order.id} {...props} />;
    default:
      return <MockCheckout key={created.order.id} {...props} />;
  }
}

type CheckoutProps = UpiPaymentSheetProps & { created: OrderCreated };

/* ------------------------------------------------------------------ Cashfree */

/**
 * Cashfree's pop-up returns nothing the server could verify, so once it closes, whatever the
 * outcome it reports, we ask the server, which asks Cashfree. A UPI request the customer
 * approves on their phone after the pop-up closed is still picked up while we wait.
 */
function CashfreeCheckout({ created, onClose, onPaid }: CheckoutProps) {
  const checkout = created.checkout;
  const [stage, setStage] = useState<"checkout" | "confirming">("checkout");
  const [attempt, setAttempt] = useState(0);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    if (stage !== "checkout") return;
    let cancelled = false;
    loadScript(checkout.checkout_script)
      .then(() => {
        if (cancelled) return;
        if (!window.Cashfree) throw new Error("Checkout failed to load");
        const cashfree = window.Cashfree({ mode: checkout.environment === "production" ? "production" : "sandbox" });
        return cashfree.checkout({ paymentSessionId: checkout.session_id, redirectTarget: "_modal" }).then((result) => {
          // `redirect`: the pop-up could not open here, so Cashfree sends the customer to the
          // return page, which confirms the payment there.
          if (!cancelled && !result.redirect) setStage("confirming");
        });
      })
      .catch(() => {
        if (cancelled) return;
        setLoadFailed(true);
        setStage("confirming");
      });
    return () => {
      cancelled = true;
    };
  }, [stage, attempt, checkout]);

  if (stage === "checkout") return null;
  return (
    <PaymentConfirmation
      order={created.order}
      gateway="Cashfree"
      loadFailed={loadFailed}
      onPaid={onPaid}
      onClose={onClose}
      onRetry={() => {
        setLoadFailed(false);
        setAttempt((n) => n + 1);
        setStage("checkout");
      }}
    />
  );
}

/** The customer may still complete the payment: nothing decided yet, or a retry is underway. */
function stillPaying({ order, payment_in_progress }: PaymentResult) {
  return order.status === "CREATED" || (order.status === "FAILED" && payment_in_progress);
}

/** Gateways send bank reasons without a closing full stop. */
function sentence(text: string) {
  const trimmed = text.trim();
  return /[.!?]$/.test(trimmed) ? trimmed : `${trimmed}.`;
}

function isGatewayOutage(error: unknown) {
  return error instanceof ApiError && error.is("GATEWAY_ERROR");
}

/** How long to keep asking the gateway on our own before leaving it to the agent. */
const CONFIRM_POLL_MS = 3000;
const CONFIRM_POLL_LIMIT_MS = 3 * 60 * 1000;

interface PaymentConfirmationProps {
  order: GatewayOrder;
  gateway: string;
  /** The checkout never opened, so there is nothing to wait for yet. */
  loadFailed?: boolean;
  onPaid: (receipt: CollectionDetail) => void;
  onClose: () => void;
  /** Open the gateway's checkout again; without it, "Try again" is not offered. */
  onRetry?: () => void;
}

/** Waits for the gateway to confirm the order's payment, through the server. */
export function PaymentConfirmation({ order, gateway, loadFailed, onPaid, onClose, onRetry }: PaymentConfirmationProps) {
  const queryClient = useQueryClient();
  const [since] = useState(() => Date.now());
  const [now, setNow] = useState(since);
  const timedOut = now - since > CONFIRM_POLL_LIMIT_MS;

  const confirmation = useQuery({
    ...paymentQueries.confirmation(order.id),
    enabled: !loadFailed,
    refetchInterval: (query) => {
      const { data, error } = query.state;
      if (error && !isGatewayOutage(error)) return false;
      if (data && !stillPaying(data)) return false;
      return Date.now() - since > CONFIRM_POLL_LIMIT_MS ? false : CONFIRM_POLL_MS;
    },
  });
  const result = confirmation.data;
  const status = result?.order.status ?? order.status;
  // An error other than an outage (the order moved to another gateway, access changed) will
  // not fix itself by asking again.
  const blocked = confirmation.error && !isGatewayOutage(confirmation.error) ? confirmation.error : null;
  const waiting = !loadFailed && !blocked && (result ? stillPaying(result) : status === "CREATED" || status === "FAILED");

  useEffect(() => {
    if (timedOut || !waiting) return;
    const timer = window.setInterval(() => setNow(Date.now()), CONFIRM_POLL_MS);
    return () => window.clearInterval(timer);
  }, [timedOut, waiting]);

  const delivered = useRef(false);
  useEffect(() => {
    const receipt = result?.receipt;
    if (result?.order.status !== "PAID" || !receipt || delivered.current) return;
    delivered.current = true;
    void Promise.all(MONEY_KEYS.map((queryKey) => queryClient.invalidateQueries({ queryKey }))).then(() => onPaid(receipt));
  }, [result, onPaid, queryClient]);

  const unreachable = isGatewayOutage(confirmation.error);
  const failed = status === "FAILED" && !waiting;

  return (
    <ResponsiveDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={status === "PAID" ? "Payment received" : waiting ? "Confirming the payment" : "Payment not completed"}
      description={`${order.customer_name} · ${order.loan_number}`}
      footer={
        <div className="flex w-full flex-col gap-2 sm:flex-row-reverse">
          {onRetry && !blocked && (status === "CREATED" || status === "FAILED") && (
            <Button size="lg" className="flex-1" onClick={onRetry}>
              <RotateCcw data-icon="inline-start" />
              {loadFailed ? "Try again" : failed ? "Try the payment again" : "Open checkout again"}
            </Button>
          )}
          {waiting && timedOut && (
            <Button size="lg" variant="outline" className="flex-1" disabled={confirmation.isFetching} onClick={() => void confirmation.refetch()}>
              {confirmation.isFetching && <Loader2 className="animate-spin" />}
              Check again
            </Button>
          )}
          <Button size="lg" variant="outline" className="flex-1" onClick={onClose}>
            {failed ? "Collect cash instead" : "Close"}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        <Money value={order.amount} quietSymbol className="text-[30px] font-medium tracking-[-0.02em] text-ink" />
        <p className="font-mono text-[11.5px] text-faint">{order.provider_order_id}</p>

        {loadFailed ? (
          <Notice tone="failed">{gateway}’s checkout could not be opened. Check the connection and try again.</Notice>
        ) : blocked ? (
          <Notice tone="failed">{blocked.message}</Notice>
        ) : status === "PAID" ? (
          <p className="flex items-center gap-2 text-[14px] text-ink">
            <Loader2 className="size-4 animate-spin" /> Opening the receipt…
          </p>
        ) : failed ? (
          <Notice tone="failed">
            {sentence(result?.order.failure_reason || "The payment did not go through")} Nothing was recorded.
          </Notice>
        ) : status === "REFUND_DUE" ? (
          <Notice tone="failed">
            The payment arrived after this loan was settled by other means, so no receipt was issued. It is marked for
            refund to the customer.
          </Notice>
        ) : status === "EXPIRED" ? (
          <Notice tone="failed">This payment request has expired. Start a new one to collect by UPI.</Notice>
        ) : (
          <>
            <p className="flex items-center gap-2 text-[14px] text-ink">
              {timedOut ? null : <Loader2 className="size-4 animate-spin text-dim" />}
              {timedOut ? "No payment yet." : `Waiting for ${gateway} to confirm…`}
            </p>
            {status === "FAILED" && (
              <p className="text-[13px] text-dim">The first attempt failed; the customer is trying again.</p>
            )}
            <p className="max-w-xs text-[13px] leading-relaxed text-dim">
              If the customer approved a UPI request on their phone, this updates by itself. The receipt is issued only
              once {gateway} confirms the money arrived.
            </p>
            {unreachable && <Notice tone="muted">{gateway} could not be reached; trying again.</Notice>}
          </>
        )}
        <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint uppercase">{gateway} · UPI</p>
      </div>
    </ResponsiveDialog>
  );
}

function Notice({ tone, children }: { tone: "failed" | "muted"; children: React.ReactNode }) {
  return (
    <p
      role={tone === "failed" ? "alert" : "status"}
      className={
        tone === "failed"
          ? "w-full rounded-lg bg-st-rejected/8 px-3.5 py-2.5 text-[13px] text-st-rejected-fg"
          : "w-full rounded-lg bg-sunk px-3.5 py-2.5 text-[13px] text-dim"
      }
    >
      {children}
    </p>
  );
}

/* ------------------------------------------------------------------ Razorpay */

function RazorpayCheckout({ created, onClose, onPaid }: CheckoutProps) {
  const verify = useVerifyPayment();
  const opened = useRef<string | null>(null);

  useEffect(() => {
    if (opened.current === created.order.provider_order_id) return;
    opened.current = created.order.provider_order_id;
    const options = created.checkout;
    void loadScript(options.checkout_script).then(() => {
      if (!window.Razorpay) return;
      const instance = new window.Razorpay({
        key: options.key_id,
        order_id: options.order_id,
        amount: options.amount_paise,
        currency: options.currency,
        name: "CashTrail",
        description: options.description,
        prefill: options.prefill,
        notes: options.notes,
        timeout: options.checkout_timeout_seconds,
        theme: { color: "#121417" },
        modal: { ondismiss: onClose },
        handler: (response: RazorpayResponse) =>
          verify.mutate(
            {
              order_id: response.razorpay_order_id,
              payment_id: response.razorpay_payment_id,
              signature: response.razorpay_signature,
            },
            { onSuccess: (result) => result.receipt && onPaid(result.receipt) },
          ),
      });
      instance.open();
    });
  }, [created, onClose, onPaid, verify]);

  return verify.isPending ? (
    <div role="status" className="fixed inset-0 z-50 grid place-items-center bg-paper/70 backdrop-blur-sm">
      <span className="flex items-center gap-2 text-[14px] text-ink">
        <Loader2 className="size-4 animate-spin" /> Confirming the payment…
      </span>
    </div>
  ) : null;
}

/* ---------------------------------------------------------------------- Mock */

function MockCheckout({ created, onClose, onPaid }: CheckoutProps) {
  const mockPay = useMockPay({ handledErrors: true });
  const order = created.order;
  const uri = `upi://pay?pa=collections@cashtrail&pn=CashTrail&am=${order.amount}&cu=INR&tn=${encodeURIComponent(order.receipt)}`;
  const failed = mockPay.data?.order.status === "FAILED" || mockPay.isError;

  return (
    <ResponsiveDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title="Ask the customer to pay"
      description={`${order.customer_name} · ${order.loan_number}`}
      footer={
        <div className="flex w-full flex-col gap-2 sm:flex-row-reverse">
          <Button
            size="lg"
            className="flex-1"
            disabled={mockPay.isPending}
            onClick={() =>
              mockPay.mutate(
                { orderId: order.id, outcome: "success" },
                { onSuccess: (result) => result.receipt && onPaid(result.receipt) },
              )
            }
          >
            {mockPay.isPending ? <Loader2 className="animate-spin" /> : <Smartphone data-icon="inline-start" />}
            Customer has paid
          </Button>
          <Button
            size="lg"
            variant="outline"
            className="flex-1"
            disabled={mockPay.isPending}
            onClick={() => mockPay.mutate({ orderId: order.id, outcome: "failure" })}
          >
            Payment failed
          </Button>
        </div>
      }
    >
      <div className="flex flex-col items-center gap-5 py-2">
        <div className="rounded-xl border border-rule bg-white p-4">
          <QRCodeSVG value={uri} size={176} level="M" fgColor="#121417" bgColor="#ffffff" />
        </div>
        <div className="flex flex-col items-center gap-1 text-center">
          <Money value={order.amount} quietSymbol className="text-[30px] font-medium tracking-[-0.02em] text-ink" />
          <p className="font-mono text-[11.5px] text-faint">{order.provider_order_id}</p>
        </div>
        <p className="max-w-xs text-center text-[13px] leading-relaxed text-dim">
          The customer scans with any UPI app. The receipt is issued only once the gateway confirms the payment.
        </p>
        {failed && (
          <p role="alert" className="w-full rounded-lg bg-st-rejected/8 px-3.5 py-2.5 text-center text-[13px] text-st-rejected-fg">
            The payment did not go through. Nothing was recorded; you can try again or collect cash.
          </p>
        )}
        <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint uppercase">Test gateway · no real money moves</p>
      </div>
    </ResponsiveDialog>
  );
}
