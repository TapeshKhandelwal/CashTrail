import { formatINRCompact } from "@/lib/format";
import { fromPaise, toPaise, type MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";

/*
 * Recharts in the ledger style: 1.5px lines (ink for expected, brand for collected and
 * settled), 7% area fills, dashed rule gridlines, mono 11px ticks, tooltips as white cards with
 * mono values. Spread these onto the Recharts primitives:
 *
 *   <CartesianGrid {...GRID} />
 *   <XAxis dataKey="date" {...AXIS} tickFormatter={formatDayMonth} />
 *   <YAxis {...AXIS} width={56} tickFormatter={chartMoneyTick} />
 *   <Area dataKey="collected" {...AREA} stroke={SERIES.collected} fill={SERIES.collected} />
 *   <Tooltip cursor={CURSOR} content={(props) => <ChartTooltip {...props} formatValue={chartMoneyTick} />} />
 */

/** Series colours. Stage colours follow the lifecycle tokens; expected is always ink. */
export const SERIES = {
  expected: "var(--ink)",
  collected: "var(--brand)",
  settled: "var(--st-settled)",
  submitted: "var(--st-submitted)",
  received: "var(--st-received)",
  deposited: "var(--st-deposited)",
  pending: "var(--st-collected)",
  short: "var(--st-short)",
  cash: "var(--ink)",
  upi: "var(--st-upi)",
} as const;

export const GRID = { stroke: "var(--rule)", strokeDasharray: "3 4", vertical: false } as const;

export const AXIS = {
  axisLine: false,
  tickLine: false,
  tickMargin: 8,
  tick: { fill: "var(--faint)", fontSize: 11, fontFamily: "var(--font-mono)" },
} as const;

export const LINE = { type: "monotone", strokeWidth: 1.5, dot: false, activeDot: { r: 3, strokeWidth: 0 } } as const;

export const AREA = { ...LINE, fillOpacity: 0.07 } as const;

export const BAR = { radius: [3, 3, 0, 0] as [number, number, number, number], maxBarSize: 28 } as const;

export const CURSOR = { stroke: "var(--rule-strong)", strokeWidth: 1, strokeDasharray: "3 3" } as const;

/** Recharts plots numbers. Fine for pixel positions; any text goes back through the money helpers. */
export function chartNumber(value: MoneyString): number {
  return Number(toPaise(value)) / 100;
}

/** Axis ticks and tooltip values: compact ₹ ("₹4.8L"). */
export function chartMoneyTick(value: number | string): string {
  return formatINRCompact(fromPaise(BigInt(Math.round(Number(value) * 100))));
}

/** Recharts animation, off under reduced motion. */
export const chartAnimation = (reduced: boolean | null) =>
  ({ isAnimationActive: !reduced, animationDuration: 600, animationEasing: "ease-out" }) as const;

interface TooltipEntry {
  name?: string | number;
  value?: number | string | ReadonlyArray<number | string>;
  color?: string;
  dataKey?: string | number | ((obj: never) => unknown);
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: ReadonlyArray<TooltipEntry>;
  label?: string | number;
  formatLabel?: (label: string | number) => string;
  formatValue?: (value: number | string) => string;
  className?: string;
}

/** White card, mono label, one row per series with its colour key and a tabular value. */
export function ChartTooltip({ active, payload, label, formatLabel, formatValue, className }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className={cn("min-w-40 rounded-lg border border-rule bg-raised px-3 py-2.5 shadow-float", className)}>
      {label !== undefined && (
        <p className="mb-1.5 font-mono text-[10.5px] tracking-[0.12em] text-faint uppercase">
          {formatLabel ? formatLabel(label) : label}
        </p>
      )}
      <ul className="flex flex-col gap-1">
        {payload.map((entry, index) => {
          const raw = Array.isArray(entry.value) ? entry.value[0] : entry.value;
          return (
            <li key={`${String(entry.dataKey ?? entry.name)}-${index}`} className="flex items-center gap-2 text-[12.5px]">
              <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: entry.color }} />
              <span className="text-dim">{entry.name}</span>
              <span className="ml-auto pl-3 font-mono text-[12px] text-ink tabular-nums">
                {raw === undefined ? "—" : formatValue ? formatValue(raw as number | string) : String(raw)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Inline legend: short colour rule + dim label, set in a row above or below the plot. */
export function ChartLegend({ items, className }: { items: { label: string; color: string; dashed?: boolean }[]; className?: string }) {
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2 text-[12.5px] text-dim">
          <span
            aria-hidden
            className="h-0.5 w-3.5 rounded-full"
            style={{
              background: item.dashed
                ? `repeating-linear-gradient(90deg, ${item.color} 0 3px, transparent 3px 5px)`
                : item.color,
            }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
