"use client";

import { useEffect, useState } from "react";

import { Money } from "@/components/money/money";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

interface LedgerEvent {
  reference: string;
  what: string;
  amount: string;
  tone: StatusTone;
  status: string;
}

// Illustrative entries in the shape of the real ledger; they cycle, newest first.
const EVENTS: readonly LedgerEvent[] = [
  { reference: "RCT-BLR01-20261017-00412", what: "Sunita Rao · EMI 7", amount: "2450.00", tone: "collected", status: "Collected" },
  { reference: "SUB-MUM01-20261017-003", what: "Counted ₹48,500 of ₹50,000", amount: "-1500.00", tone: "short", status: "Short" },
  { reference: "RCT-DEL01-20261017-00188", what: "Imran Sheikh · UPI", amount: "3100.00", tone: "upi", status: "UPI" },
  { reference: "SUB-BLR01-20261017-005", what: "Handed over by Ravi K.", amount: "12450.00", tone: "submitted", status: "Submitted" },
  { reference: "DEP-DEL01-20261016-001", what: "HDFC ••4821 · slip 77310", amount: "312400.00", tone: "settled", status: "Settled" },
  { reference: "SUB-BLR01-20261017-004", what: "Counted ₹36,200 · matches", amount: "36200.00", tone: "received", status: "At branch" },
  { reference: "DEP-MUM01-20261017-002", what: "ICICI ••0937 · slip 41187", amount: "148000.00", tone: "deposited", status: "Deposited" },
];

const VISIBLE = 5;
const EVERY_MS = 3200;
const FIRST_MINUTE = 9 * 60 + 12;
const MINUTES_APART = 13;

/** Entries are 13 minutes apart from 09:12, so the newest row always carries the latest time. */
function timeOf(sequence: number): string {
  const minutes = (FIRST_MINUTE + sequence * MINUTES_APART) % (24 * 60);
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

/** The quiet half of the sign-in page: ledger ruling and a mini-ledger that keeps writing. */
export function LoginLedger() {
  const [head, setHead] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = setInterval(() => setHead((value) => value + 1), EVERY_MS);
    return () => clearInterval(timer);
  }, []);

  // Start a few entries in, so the first screen already shows a full ledger.
  const rows = Array.from({ length: VISIBLE }, (_, index) => {
    const sequence = head + VISIBLE - 1 - index;
    return { event: EVENTS[sequence % EVENTS.length], sequence };
  });

  return (
    <div className="relative flex h-full flex-col justify-between gap-12 overflow-hidden p-10 xl:p-14">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(to_bottom,transparent_0_35px,color-mix(in_oklab,var(--rule)_75%,transparent)_35px_36px)] [mask-image:linear-gradient(to_bottom,black,transparent_92%)]"
      />
      <div aria-hidden className="pointer-events-none absolute inset-y-0 left-14 w-px bg-st-rejected/25 xl:left-[72px]" />

      <p className="relative flex items-center gap-2.5 pl-8 xl:pl-10">
        <span className="relative flex size-1.5">
          <span className="absolute inline-flex size-full animate-pulse-ring rounded-full bg-brand" />
          <span className="relative inline-flex size-1.5 rounded-full bg-brand" />
        </span>
        <span className="eyebrow">Ledger · all branches · today</span>
      </p>

      <div className="relative pl-8 xl:pl-10" aria-hidden>
        <div className="overflow-hidden rounded-xl border border-rule bg-raised shadow-float">
          <div className="grid grid-cols-[3rem_1fr_auto] gap-3 border-b border-rule bg-sunk px-4 py-2.5 font-mono text-[10px] tracking-[0.14em] text-faint uppercase">
            <span>Time</span>
            <span>Entry</span>
            <span className="text-right">Amount</span>
          </div>
          <ol>
            {rows.map(({ event, sequence }, index) => {
              const tone = TONE_CLASSES[event.tone];
              return (
                <li
                  key={sequence}
                  className={cn(
                    "grid grid-cols-[3rem_1fr_auto] items-center gap-3 border-b border-rule px-4 py-3 last:border-b-0",
                    index === 0 && "animate-rise bg-brand-tint/40",
                    index > 2 && "opacity-70",
                  )}
                >
                  <span className="font-mono text-[11px] text-faint tabular-nums">{timeOf(sequence)}</span>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate font-mono text-[11.5px] text-ink">{event.reference}</span>
                    <span className="truncate text-[12.5px] text-dim">{event.what}</span>
                  </span>
                  <span className="flex flex-col items-end gap-1">
                    <Money value={event.amount} tone={event.tone === "short" ? "short" : "none"} className="text-[13px] font-medium" />
                    <span className={cn("flex items-center gap-1.5 text-[11px]", tone.text)}>
                      <span className={cn("size-1.5 rounded-full", tone.dot)} />
                      {event.status}
                    </span>
                  </span>
                </li>
              );
            })}
          </ol>
        </div>
      </div>

      <div className="relative pl-8 xl:pl-10">
        <p className="font-display text-[clamp(1.9rem,2.6vw,2.5rem)] leading-[1.05] text-ink">
          Five hand-offs.
          <br />
          <span className="text-dim">One ledger.</span>
        </p>
        <p className="mt-5 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] tracking-[0.08em] text-faint uppercase">
          <span>Receipt</span>
          <span aria-hidden className="text-rule-strong">/</span>
          <span>Count</span>
          <span aria-hidden className="text-rule-strong">/</span>
          <span>Deposit</span>
          <span aria-hidden className="text-rule-strong">/</span>
          <span>Settle</span>
        </p>
      </div>
    </div>
  );
}
