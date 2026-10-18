"use client";

import { useEffect, useState } from "react";

import { Money } from "@/components/money/money";
import { formatINR } from "@/lib/format";
import { absMoney, compareMoney, subMoney, toPaise, type MoneyString } from "@/lib/money";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

export type VarianceState = "match" | "short" | "excess";

/** counted − expected: negative is short, positive is excess. */
export function varianceOf(expected: MoneyString, counted: MoneyString): { state: VarianceState; difference: MoneyString } {
  const difference = subMoney(counted, expected);
  const order = compareMoney(counted, expected);
  return { state: order === 0 ? "match" : order < 0 ? "short" : "excess", difference };
}

export function varianceLabel(state: VarianceState, difference: MoneyString): string {
  if (state === "match") return "Matches";
  return `${formatINR(absMoney(difference))} ${state === "short" ? "short" : "excess"}`;
}

const STATE_TONE: Record<VarianceState, StatusTone> = { match: "settled", short: "short", excess: "excess" };

function widthOf(part: MoneyString, scale: bigint): string {
  if (scale <= 0n) return "0%";
  return `${Number((toPaise(part) * 10_000n) / scale) / 100}%`;
}

/**
 * Expected against counted on one scale, with the difference in words and colour: "Matches",
 * "₹500.00 short", "₹200.00 excess". Announced politely once counting pauses.
 */
export function VarianceMeter({
  expected,
  counted,
  expectedLabel = "Expected",
  countedLabel = "Counted",
  className,
}: {
  expected: MoneyString;
  counted: MoneyString;
  expectedLabel?: string;
  countedLabel?: string;
  className?: string;
}) {
  const { state, difference } = varianceOf(expected, counted);
  const scale = compareMoney(expected, counted) >= 0 ? toPaise(expected) : toPaise(counted);
  const label = varianceLabel(state, difference);
  const tone = TONE_CLASSES[STATE_TONE[state]];
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setAnnouncement(`Variance: ${label}`), 400);
    return () => clearTimeout(timer);
  }, [label]);

  const rows = [
    { name: expectedLabel, amount: expected, bar: "bg-ink/70" },
    { name: countedLabel, amount: counted, bar: tone.dot },
  ];

  return (
    <div className={cn("flex flex-col gap-3.5", className)}>
      {rows.map((row) => (
        <div key={row.name} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3 text-[13.5px]">
            <span className="text-dim">{row.name}</span>
            <Money value={row.amount} className="font-medium text-ink" />
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-sunk">
            <div
              className={cn("h-full rounded-full transition-[width,background-color] duration-300 ease-out-quint", row.bar)}
              style={{ width: widthOf(row.amount, scale) }}
            />
          </div>
        </div>
      ))}
      <div className={cn("flex items-center justify-between rounded-lg px-3 py-2.5 transition-colors duration-200", tone.wash)}>
        <span className="eyebrow">Difference</span>
        <span className={cn("flex items-center gap-2 text-[14px] font-medium tabular-nums", tone.text)}>
          <span aria-hidden className={cn("size-1.5 rounded-full transition-colors duration-200", tone.dot)} />
          {label}
        </span>
      </div>
      <span className="sr-only" aria-live="polite">
        {announcement}
      </span>
    </div>
  );
}
