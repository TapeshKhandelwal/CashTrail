/**
 * The single source of truth for status -> tone / label / icon. Every chip, timeline node and
 * lifecycle chart reads from here; never map backend enums to colours anywhere else.
 */
import {
  Ban,
  Banknote,
  BadgeCheck,
  Building,
  CalendarClock,
  CalendarX2,
  CircleX,
  Clock,
  HandCoins,
  Landmark,
  OctagonAlert,
  SendHorizontal,
  Smartphone,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { daysBetween, formatDayMonth, todayIST } from "@/lib/dates";
import { formatINR } from "@/lib/format";
import { absMoney, isNegative, isZero } from "@/lib/money";
import type {
  CollectionStatus,
  DepositStatus,
  DiscrepancyDirection,
  DiscrepancyStatus,
  GatewayOrderStatus,
  InstallmentStatus,
  LoanStatus,
  Money,
  PaymentMode,
  SubmissionStatus,
} from "@/types/domain";

export const STATUS_TONES = [
  "expected",
  "collected",
  "submitted",
  "received",
  "deposited",
  "settled",
  "rejected",
  "failed",
  "voided",
  "short",
  "excess",
  "delayed",
  "upi",
] as const;
export type StatusTone = (typeof STATUS_TONES)[number];

export interface StatusMeta {
  tone: StatusTone;
  label: string;
  icon: LucideIcon;
  /** Amount struck through (voided receipts). */
  strike?: boolean;
}

/**
 * Literal class strings per tone so Tailwind can see them.
 * dot: 6px marker · text: AA label colour · wash: ~7% background · rule: 2px top rule colour ·
 * stroke / fill: SVG marks.
 */
export const TONE_CLASSES: Record<
  StatusTone,
  { dot: string; text: string; wash: string; rule: string; border: string; stroke: string; fill: string }
> = {
  expected: {
    dot: "bg-st-expected",
    text: "text-st-expected-fg",
    wash: "bg-st-expected/8",
    rule: "border-t-st-expected",
    border: "border-st-expected",
    stroke: "stroke-st-expected",
    fill: "fill-st-expected",
  },
  collected: {
    dot: "bg-st-collected",
    text: "text-st-collected-fg",
    wash: "bg-st-collected/8",
    rule: "border-t-st-collected",
    border: "border-st-collected",
    stroke: "stroke-st-collected",
    fill: "fill-st-collected",
  },
  submitted: {
    dot: "bg-st-submitted",
    text: "text-st-submitted-fg",
    wash: "bg-st-submitted/8",
    rule: "border-t-st-submitted",
    border: "border-st-submitted",
    stroke: "stroke-st-submitted",
    fill: "fill-st-submitted",
  },
  received: {
    dot: "bg-st-received",
    text: "text-st-received-fg",
    wash: "bg-st-received/8",
    rule: "border-t-st-received",
    border: "border-st-received",
    stroke: "stroke-st-received",
    fill: "fill-st-received",
  },
  deposited: {
    dot: "bg-st-deposited",
    text: "text-st-deposited-fg",
    wash: "bg-st-deposited/8",
    rule: "border-t-st-deposited",
    border: "border-st-deposited",
    stroke: "stroke-st-deposited",
    fill: "fill-st-deposited",
  },
  settled: {
    dot: "bg-st-settled",
    text: "text-st-settled-fg",
    wash: "bg-st-settled/8",
    rule: "border-t-st-settled",
    border: "border-st-settled",
    stroke: "stroke-st-settled",
    fill: "fill-st-settled",
  },
  rejected: {
    dot: "bg-st-rejected",
    text: "text-st-rejected-fg",
    wash: "bg-st-rejected/8",
    rule: "border-t-st-rejected",
    border: "border-st-rejected",
    stroke: "stroke-st-rejected",
    fill: "fill-st-rejected",
  },
  failed: {
    dot: "bg-st-failed",
    text: "text-st-failed-fg",
    wash: "bg-st-failed/8",
    rule: "border-t-st-failed",
    border: "border-st-failed",
    stroke: "stroke-st-failed",
    fill: "fill-st-failed",
  },
  voided: {
    dot: "bg-st-voided",
    text: "text-st-voided-fg",
    wash: "bg-st-voided/8",
    rule: "border-t-st-voided",
    border: "border-st-voided",
    stroke: "stroke-st-voided",
    fill: "fill-st-voided",
  },
  short: {
    dot: "bg-st-short",
    text: "text-st-short-fg",
    wash: "bg-st-short/8",
    rule: "border-t-st-short",
    border: "border-st-short",
    stroke: "stroke-st-short",
    fill: "fill-st-short",
  },
  excess: {
    dot: "bg-st-excess",
    text: "text-st-excess-fg",
    wash: "bg-st-excess/8",
    rule: "border-t-st-excess",
    border: "border-st-excess",
    stroke: "stroke-st-excess",
    fill: "fill-st-excess",
  },
  delayed: {
    dot: "bg-st-delayed",
    text: "text-st-delayed-fg",
    wash: "bg-st-delayed/8",
    rule: "border-t-st-delayed",
    border: "border-st-delayed",
    stroke: "stroke-st-delayed",
    fill: "fill-st-delayed",
  },
  upi: {
    dot: "bg-st-upi",
    text: "text-st-upi-fg",
    wash: "bg-st-upi/8",
    rule: "border-t-st-upi",
    border: "border-st-upi",
    stroke: "stroke-st-upi",
    fill: "fill-st-upi",
  },
};

/** CSS colour for charts, SVG and inline styles: `toneColor("settled")` -> "var(--st-settled)". */
export const toneColor = (tone: StatusTone) => `var(--st-${tone})`;

/* ----------------------------------------------------------- Collections */

const COLLECTION: Record<CollectionStatus, StatusMeta> = {
  COLLECTED: { tone: "collected", label: "Collected", icon: HandCoins },
  SUBMITTED: { tone: "submitted", label: "Submitted", icon: SendHorizontal },
  BRANCH_RECEIVED: { tone: "received", label: "At branch", icon: Building },
  DEPOSITED: { tone: "deposited", label: "Deposited", icon: Landmark },
  SETTLED: { tone: "settled", label: "Settled", icon: BadgeCheck },
  VOIDED: { tone: "voided", label: "Voided", icon: Ban, strike: true },
};

export const collectionStatus = (status: CollectionStatus): StatusMeta => COLLECTION[status];

/** The cash lifecycle, in order (UPI goes Collected -> Settled). */
export const CASH_LIFECYCLE: CollectionStatus[] = ["COLLECTED", "SUBMITTED", "BRANCH_RECEIVED", "DEPOSITED", "SETTLED"];

/* ----------------------------------------------------------- Submissions */

/** `difference` is expected minus received: positive means short, negative means excess. */
export function submissionStatus(status: SubmissionStatus, difference?: Money | null): StatusMeta {
  switch (status) {
    case "SUBMITTED":
      return { tone: "submitted", label: "Awaiting count", icon: SendHorizontal };
    case "APPROVED":
      return { tone: "received", label: "Approved", icon: Building };
    case "APPROVED_WITH_DISCREPANCY": {
      if (!difference || isZero(difference)) {
        return { tone: "short", label: "Approved · variance", icon: TriangleAlert };
      }
      const excess = isNegative(difference);
      return {
        tone: excess ? "excess" : "short",
        label: `Approved · ${formatINR(absMoney(difference), { whole: true })} ${excess ? "excess" : "short"}`,
        icon: TriangleAlert,
      };
    }
    case "REJECTED":
      return { tone: "rejected", label: "Rejected", icon: CircleX };
  }
}

/* -------------------------------------------------------------- Deposits */

export function depositStatus(
  status: DepositStatus,
  delay?: { isDelayed: boolean; daysPending: number | null },
): StatusMeta {
  switch (status) {
    case "PENDING":
      if (delay?.isDelayed) {
        return { tone: "delayed", label: `Delayed ${delay.daysPending ?? 0}d`, icon: Clock };
      }
      return { tone: "deposited", label: "Pending", icon: Landmark };
    case "SETTLED":
      return { tone: "settled", label: "Settled", icon: BadgeCheck };
    case "SETTLED_WITH_MISMATCH":
      return { tone: "short", label: "Settled · mismatch", icon: TriangleAlert };
    case "FAILED":
      return { tone: "failed", label: "Failed", icon: OctagonAlert };
  }
}

/* --------------------------------------------------------- Discrepancies */

export function discrepancyStatus(status: DiscrepancyStatus, direction: DiscrepancyDirection = "SHORT"): StatusMeta {
  switch (status) {
    case "OPEN":
      return { tone: direction === "EXCESS" ? "excess" : "short", label: "Open", icon: TriangleAlert };
    case "RESOLVED":
      return { tone: "settled", label: "Resolved", icon: BadgeCheck };
    case "WRITTEN_OFF":
      return { tone: "voided", label: "Written off", icon: Ban };
  }
}

/* ---------------------------------------------------------- Installments */

export function installmentStatus(
  installment: { status: InstallmentStatus; is_overdue: boolean; due_date: string },
  today: string = todayIST(),
): StatusMeta {
  if (installment.status === "PAID") return { tone: "settled", label: "Paid", icon: BadgeCheck };
  if (installment.is_overdue) {
    const days = Math.max(1, daysBetween(installment.due_date, today));
    return { tone: "short", label: `Overdue ${days}d`, icon: CalendarX2 };
  }
  if (installment.status === "PARTIALLY_PAID") return { tone: "collected", label: "Part paid", icon: HandCoins };
  return { tone: "expected", label: `Due ${formatDayMonth(installment.due_date)}`, icon: CalendarClock };
}

/* -------------------------------------------------------- Gateway orders */

const GATEWAY_ORDER: Record<GatewayOrderStatus, StatusMeta> = {
  CREATED: { tone: "expected", label: "Awaiting payment", icon: CalendarClock },
  PAID: { tone: "collected", label: "Paid", icon: HandCoins },
  FAILED: { tone: "failed", label: "Payment failed", icon: OctagonAlert },
  EXPIRED: { tone: "voided", label: "Expired", icon: Ban },
  REFUND_DUE: { tone: "short", label: "Refund due", icon: TriangleAlert },
};

export const gatewayOrderStatus = (status: GatewayOrderStatus): StatusMeta => GATEWAY_ORDER[status];

/* ----------------------------------------------------------------- Loans */

const LOAN: Record<LoanStatus, StatusMeta> = {
  ACTIVE: { tone: "collected", label: "Active", icon: HandCoins },
  CLOSED: { tone: "settled", label: "Closed", icon: BadgeCheck },
};

export const loanStatus = (status: LoanStatus): StatusMeta => LOAN[status];

/* -------------------------------------------------------- Payment modes */

/** Payment mode is a neutral marker, not a status: Cash in ink, UPI in the UPI colour. */
export const PAYMENT_MODE: Record<PaymentMode, { label: string; icon: LucideIcon; className: string }> = {
  CASH: { label: "Cash", icon: Banknote, className: "text-ink" },
  UPI: { label: "UPI", icon: Smartphone, className: "text-st-upi-fg" },
};
