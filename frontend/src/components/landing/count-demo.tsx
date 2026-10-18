"use client";

import { Minus, Plus } from "lucide-react";
import { useState } from "react";

import { Money } from "@/components/money/money";
import { Button } from "@/components/ui/button";
import { fromPaise, toPaise, type MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";

const EXPECTED: MoneyString = "50000.00";
const NOTES = [500, 200, 100] as const;
const START: Record<(typeof NOTES)[number], number> = { 500: 85, 200: 20, 100: 20 };

interface Entry {
  id: number;
  label: string;
  amount: MoneyString;
  tone: "short" | "excess" | "match";
}

/**
 * The brief's own example, live: ₹50,000 receipted, ₹48,500 in the bag. Change the count and
 * the difference, the action and the ledger entry follow. Exact paise maths throughout.
 */
export function CountDemo() {
  const [counts, setCounts] = useState(START);
  const [ledger, setLedger] = useState<Entry[]>([]);

  const counted = fromPaise(NOTES.reduce((total, note) => total + BigInt(note * counts[note]) * 100n, 0n));
  const difference = toPaise(counted) - toPaise(EXPECTED);
  const state = difference === 0n ? "match" : difference < 0n ? "short" : "excess";
  const gap = fromPaise(difference < 0n ? -difference : difference);

  const step = (note: (typeof NOTES)[number], by: number) =>
    setCounts((current) => ({ ...current, [note]: Math.max(0, current[note] + by) }));

  const approve = () =>
    setLedger((current) => [
      {
        id: Date.now(),
        label: state === "match" ? "Accepted · matches receipts" : state === "short" ? "Cash shortage raised · Ravi Kumar" : "Cash excess raised · Ravi Kumar",
        amount: state === "match" ? counted : gap,
        tone: state,
      },
      ...current.slice(0, 2),
    ]);

  return (
    <div className="mx-auto grid w-full max-w-5xl grid-cols-[minmax(0,1fr)] overflow-hidden rounded-2xl border border-rule bg-raised shadow-float md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-col gap-5 border-rule p-5 max-md:border-b md:border-r sm:p-8">
        <div className="flex items-baseline justify-between gap-3">
          <span className="eyebrow">
            Receipted · <span className="whitespace-nowrap">14 receipts</span>
          </span>
          <Money value={EXPECTED} className="text-[15px] text-ink" />
        </div>
        <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule">
          {NOTES.map((note) => (
            <li key={note} className="flex items-center gap-3 px-4 py-3 max-sm:py-2.5 max-sm:pr-2.5">
              <span className="flex min-w-0 flex-1 flex-col gap-0.5 lg:w-16 lg:flex-none">
                <span className="font-mono text-[14px] text-ink">₹{note}</span>
                <Money value={fromPaise(BigInt(note * counts[note]) * 100n)} className="text-[12px] text-dim lg:hidden" />
              </span>
              <div className="ml-auto flex items-center gap-1.5">
                <button type="button" aria-label={`One less ₹${note} note`} onClick={() => step(note, -1)} className="grid size-11 place-items-center rounded-lg sm:size-9 border border-rule-strong text-dim transition-colors hover:border-ink/30 hover:text-ink active:translate-y-px">
                  <Minus className="size-3.5" />
                </button>
                <span className="w-10 text-center font-mono text-[15px] text-ink tabular-nums" aria-live="polite">
                  {counts[note]}
                </span>
                <button type="button" aria-label={`One more ₹${note} note`} onClick={() => step(note, 1)} className="grid size-11 place-items-center rounded-lg sm:size-9 border border-rule-strong text-dim transition-colors hover:border-ink/30 hover:text-ink active:translate-y-px">
                  <Plus className="size-3.5" />
                </button>
              </div>
              <Money value={fromPaise(BigInt(note * counts[note]) * 100n)} className="w-24 text-right text-[13px] text-dim max-lg:hidden" />
            </li>
          ))}
        </ul>
        <div className="flex items-baseline justify-between gap-3 rounded-xl bg-sunk px-4 py-3.5">
          <span className="eyebrow">Counted</span>
          <Money value={counted} quietSymbol className="text-[clamp(1.375rem,6.5vw,1.625rem)] font-medium tracking-[-0.02em] text-ink" />
        </div>
      </div>

      <div className="flex flex-col gap-5 p-5 sm:p-8">
        <div className="flex flex-col gap-1.5">
          <span className="eyebrow">Difference</span>
          <p
            className={cn(
              "text-[clamp(2rem,10vw,2.375rem)] leading-none font-medium tracking-[-0.025em] tabular-nums transition-colors duration-300",
              state === "match" ? "text-st-settled-fg" : state === "short" ? "text-st-short-fg" : "text-st-excess-fg",
            )}
          >
            {state === "match" ? "Matches" : <><span>{state === "short" ? "−" : "+"}</span><Money value={gap} quietSymbol /></>}
          </p>
          <p className="text-[13.5px] text-dim">
            {state === "match"
              ? "The count agrees with every receipt."
              : state === "short"
                ? "Less cash than receipts. It is recorded against the agent, not hidden in the branch's total."
                : "More cash than receipts. The surplus is recorded, not quietly absorbed."}
          </p>
        </div>

        <Button size="lg" variant={state === "match" ? "default" : "outline"} onClick={approve} className={cn("max-sm:h-11", state !== "match" && "border-st-short/40 text-st-short-fg hover:bg-st-short/6")}>
          {state === "match" ? "Accept the cash" : "Accept with discrepancy"}
        </Button>

        <div className="flex flex-col gap-2">
          <span className="eyebrow">Ledger</span>
          {ledger.length === 0 ? (
            <p className="rounded-lg border border-dashed border-rule-strong px-4 py-3.5 text-[13px] text-faint">Nothing recorded yet. Accept the count to see the entry.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-rule overflow-hidden rounded-lg border border-rule">
              {ledger.map((entry) => (
                <li key={entry.id} className="animate-rise flex items-center justify-between gap-3 px-4 py-3">
                  <span className="min-w-0 text-[13px] text-ink">{entry.label}</span>
                  <Money value={entry.amount} tone={entry.tone === "match" ? "settled" : entry.tone} className="shrink-0 text-[13px]" />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
