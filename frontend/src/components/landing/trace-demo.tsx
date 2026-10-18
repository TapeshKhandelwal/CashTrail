"use client";

import { Lock, RotateCcw } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const STAGES: { label: string; tone: StatusTone; who: string; when: string; reference: string; detail: string }[] = [
  {
    label: "Collected",
    tone: "collected",
    who: "Ravi Kumar, agent",
    when: "17 Oct · 09:12",
    reference: "RCT-BLR01-20261017-00412",
    detail: "Receipt issued at the doorstep. The cash is now Ravi's responsibility.",
  },
  {
    label: "Submitted",
    tone: "submitted",
    who: "Ravi Kumar, agent",
    when: "17 Oct · 18:30",
    reference: "SUB-BLR01-20261017-005",
    detail: "Handed to the branch with six other receipts, ₹31,954.62 in all.",
  },
  {
    label: "Branch received",
    tone: "received",
    who: "Kavitha Rao, branch manager",
    when: "18 Oct · 10:30",
    reference: "SUB-BLR01-20261017-005",
    detail: "Counted note by note. It matched the receipts to the paisa.",
  },
  {
    label: "Deposited",
    tone: "deposited",
    who: "Kavitha Rao, branch manager",
    when: "18 Oct · 14:00",
    reference: "DEP-BLR01-20261018-001",
    detail: "Banked at HDFC ••4821 on slip 77310, with the day's other counted cash.",
  },
  {
    label: "Settled",
    tone: "settled",
    who: "Priya Raghavan, finance",
    when: "19 Oct · 11:05",
    reference: "STMT-20261019-9812",
    detail: "Matched to the bank statement. The receipt is now locked.",
  },
];

/** A single receipt walked through the five hand-offs, ending with an edit the database refuses. */
export function TraceDemo() {
  const [stage, setStage] = useState(0);
  const [tampered, setTampered] = useState(false);
  const settled = stage === STAGES.length - 1;
  const current = STAGES[stage];

  return (
    <div className="mx-auto w-full max-w-4xl overflow-hidden rounded-2xl border border-rule bg-raised shadow-float">
      <div className="flex items-center gap-2 border-b border-rule bg-sunk px-4 py-2.5">
        <span className="size-2 rounded-full bg-st-rejected/50" />
        <span className="size-2 rounded-full bg-st-collected/50" />
        <span className="size-2 rounded-full bg-st-settled/50" />
        <span className="ml-2 min-w-0 truncate font-mono text-[10.5px] tracking-[0.14em] text-faint uppercase">
          <span className="max-sm:hidden">receipt · </span>RCT-BLR01-20261017-00412
        </span>
      </div>

      <div className="grid md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="flex flex-col gap-5 border-rule p-5 max-md:border-b md:border-r sm:p-8">
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span className="eyebrow">Payment receipt</span>
              <span className="text-[15px] text-ink">Sunita Rao</span>
              <span className="font-mono text-[11.5px] text-faint">
                LN-BLR01-000045 · <span className="whitespace-nowrap">EMI 7 of 12</span>
              </span>
            </div>
            <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[12px] font-medium transition-colors duration-300", TONE_CLASSES[current.tone].wash, TONE_CLASSES[current.tone].text)}>
              <span className={cn("size-1.5 rounded-full transition-colors duration-300", TONE_CLASSES[current.tone].dot)} />
              {current.label}
            </span>
          </div>
          <div className="border-y border-dashed border-rule-strong py-5">
            <p className="text-[clamp(2rem,10vw,2.375rem)] leading-none font-medium tracking-[-0.025em] text-ink tabular-nums">
              <span className="mr-1 text-[0.6em] font-normal text-dim">₹</span>2,450.00
            </p>
            <p className="mt-2 text-[13px] text-dim">Two thousand four hundred fifty rupees only</p>
          </div>
          <div className="relative min-h-[88px] rounded-lg bg-sunk px-4 py-3.5 max-sm:min-h-[106px]">
            {tampered ? (
              <div role="status" className="animate-rise flex flex-col gap-1.5">
                <span className="font-mono text-[11px] tracking-[0.1em] text-st-rejected-fg uppercase">409 · record_locked</span>
                <span className="text-[13.5px] leading-relaxed text-ink">
                  Changing the amount was refused by the database itself. Corrections go in as new, audited entries.
                </span>
              </div>
            ) : (
              <p key={stage} className="animate-rise text-[13.5px] leading-relaxed text-ink">
                {current.detail}
              </p>
            )}
          </div>
          <div className="mt-auto flex flex-wrap gap-2 max-sm:flex-col">
            {settled ? (
              <>
                <Button variant="outline" size="sm" onClick={() => setTampered(true)} disabled={tampered} className="max-sm:h-11 max-sm:text-sm">
                  <Lock data-icon="inline-start" />
                  Try to change the amount
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="max-sm:h-11 max-sm:text-sm"
                  onClick={() => {
                    setStage(0);
                    setTampered(false);
                  }}
                >
                  <RotateCcw data-icon="inline-start" />
                  Start again
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={() => setStage((value) => value + 1)} className="max-sm:h-11 max-sm:text-sm">
                Next hand-off: {STAGES[stage + 1].label}
              </Button>
            )}
          </div>
        </div>

        <ol className="flex flex-col p-5 sm:p-8">
          {STAGES.map((item, index) => {
            const reached = index <= stage;
            const tone = TONE_CLASSES[item.tone];
            return (
              <li key={item.label} className="relative flex gap-4 pb-6 last:pb-0">
                {index < STAGES.length - 1 && (
                  <span aria-hidden className={cn("absolute top-4 left-[5px] h-full w-px transition-colors duration-500", index < stage ? tone.dot : "bg-rule")} />
                )}
                <button
                  type="button"
                  onClick={() => {
                    setStage(index);
                    setTampered(false);
                  }}
                  aria-label={`Show ${item.label}`}
                  className={cn(
                    "relative mt-1 size-[11px] shrink-0 rounded-full border-2 transition-all duration-300 after:absolute after:-inset-4 after:content-['']",
                    reached ? cn(tone.dot, "border-transparent") : "border-rule-strong bg-raised",
                    index === stage && "ring-4 ring-focus/60",
                  )}
                />
                <div className={cn("flex min-w-0 flex-col gap-0.5 transition-opacity duration-300", reached ? "opacity-100" : "opacity-40")}>
                  <span className="text-[14px] text-ink">{item.label}</span>
                  <span className="text-[12.5px] text-dim">{item.who}</span>
                  <span className="font-mono text-[11px] text-faint sm:truncate">
                    {item.when}
                    <span className="max-sm:hidden"> · </span>
                    <span className="max-sm:block">{item.reference}</span>
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
