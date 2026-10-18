import { formatINR, formatINRCompact } from "@/lib/format";
import { absMoney, isNegative, isPositive, type MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";

export type MoneyTone =
  /** Ink (inherits). */
  | "none"
  /** Variances: negative in the short colour, positive in the excess colour. */
  | "direction"
  | "short"
  | "excess"
  | "settled"
  | "dim";

const TONE: Record<Exclude<MoneyTone, "direction">, string | undefined> = {
  none: undefined,
  short: "text-st-short-fg",
  excess: "text-st-excess-fg",
  settled: "text-st-settled-fg",
  dim: "text-dim",
};

interface MoneyProps {
  value: MoneyString;
  /** "₹4.8L" style: charts and tight KPI spots only. */
  compact?: boolean;
  /** Whole rupees. Never on receipts or confirmations. */
  whole?: boolean;
  /** "+" on positive amounts (variances, deltas). Negatives always carry a minus. */
  signed?: boolean;
  tone?: MoneyTone;
  /** Set the ₹ smaller and dim: KPI figures and receipt totals. */
  quietSymbol?: boolean;
  /** Set the paise dim: long tables of amounts. */
  quietPaise?: boolean;
  /** Voided amounts are struck through. */
  strike?: boolean;
  className?: string;
}

/**
 * Every amount on screen: Indian grouping, tabular figures, exact (string) value.
 *
 *   <Money value={row.amount} />                         ₹48,500.00
 *   <Money value={variance} signed tone="direction" />   −₹500.00 in the short colour
 *   <Money value={kpi} whole quietSymbol className="figure" />
 */
export function Money({
  value,
  compact = false,
  whole = false,
  signed = false,
  tone = "none",
  quietSymbol = false,
  quietPaise = false,
  strike = false,
  className,
}: MoneyProps) {
  const negative = isNegative(value);
  const abs = absMoney(value);
  const text = (compact ? formatINRCompact(abs) : formatINR(abs, { whole })).replace("₹", "");
  const sign = negative ? "−" : signed && isPositive(value) ? "+" : "";
  const dot = text.lastIndexOf(".");
  const splitPaise = quietPaise && !compact && !whole && dot > 0;

  const toneClass =
    tone === "direction" ? (negative ? TONE.short : isPositive(value) ? TONE.excess : undefined) : TONE[tone];

  return (
    <span
      className={cn(
        "whitespace-nowrap tabular-nums",
        toneClass,
        strike && "line-through decoration-1",
        className,
      )}
    >
      {sign}
      <span className={cn(quietSymbol && "mr-[0.06em] text-[0.72em] font-normal text-dim")}>₹</span>
      {splitPaise ? (
        <>
          {text.slice(0, dot)}
          <span className="text-faint">{text.slice(dot)}</span>
        </>
      ) : (
        text
      )}
    </span>
  );
}
