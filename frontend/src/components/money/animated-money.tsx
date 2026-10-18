"use client";

import NumberFlow from "@number-flow/react";

import { asNumeric } from "@/lib/format";
import { absMoney, isNegative, type MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";

const WHOLE = { maximumFractionDigits: 0 } as const;
const PAISE = { minimumFractionDigits: 2, maximumFractionDigits: 2 } as const;

/**
 * A KPI or running total that rolls when its value changes (never on first render). The ₹ is
 * set smaller and dim. Use static <Money> for receipts and confirmations.
 *
 *   <AnimatedMoney value={summary.cash_in_hand} className="figure" />
 */
export function AnimatedMoney({
  value,
  paise = false,
  quietSymbol = true,
  className,
}: {
  value: MoneyString;
  /** Show paise (counted totals); KPIs round to rupees. */
  paise?: boolean;
  quietSymbol?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-baseline whitespace-nowrap tabular-nums", className)}>
      {isNegative(value) && "−"}
      <span className={cn(quietSymbol && "mr-[0.06em] text-[0.72em] font-normal text-dim")}>₹</span>
      <NumberFlow value={asNumeric(absMoney(value))} locales="en-IN" format={paise ? PAISE : WHOLE} willChange />
    </span>
  );
}

/** A rolling integer (receipts, visits, counts). */
export function AnimatedCount({ value, className }: { value: number; className?: string }) {
  return (
    <span className={cn("inline-flex tabular-nums", className)}>
      <NumberFlow value={value} locales="en-IN" />
    </span>
  );
}
