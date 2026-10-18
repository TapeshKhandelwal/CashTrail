import { Ban, Clock3, Copy, Database, Lock, RotateCcw, Scale, ShieldAlert, Webhook, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Spotlight } from "@/components/motion/spotlight";
import { cn } from "@/lib/utils";

interface Case {
  condition: string;
  outcome: string;
  tint: string;
  outcomeClass: string;
  icon: LucideIcon;
  span?: string;
  visual?: ReactNode;
}

const CASES: Case[] = [
  {
    condition: "Same receipt sent twice",
    outcome: "Returned, not duplicated",
    tint: "var(--st-received)",
    outcomeClass: "text-st-received-fg",
    icon: Copy,
    span: "col-span-2",
    visual: (
      <div className="mt-5 flex flex-col gap-1.5 font-mono text-[11px]">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 rounded-lg border border-rule bg-sunk px-3 py-2">
          <span className="text-ink">POST /collections · key 7f3c…</span>
          <span className="text-st-settled-fg">201 created</span>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 rounded-lg border border-rule bg-sunk px-3 py-2">
          <span className="text-ink">POST /collections · key 7f3c…</span>
          <span className="text-st-received-fg">200 · same receipt</span>
        </div>
      </div>
    ),
  },
  {
    condition: "More than the balance",
    outcome: "Refused",
    tint: "var(--st-rejected)",
    outcomeClass: "text-st-rejected-fg",
    icon: Scale,
  },
  {
    condition: "Counted short at the branch",
    outcome: "Discrepancy raised",
    tint: "var(--st-short)",
    outcomeClass: "text-st-short-fg",
    icon: ShieldAlert,
  },
  {
    condition: "Bank reference reused",
    outcome: "Blocked",
    tint: "var(--st-rejected)",
    outcomeClass: "text-st-rejected-fg",
    icon: Lock,
  },
  {
    condition: "Edit after reconciliation",
    outcome: "Refused by the database",
    tint: "var(--st-settled)",
    outcomeClass: "text-st-settled-fg",
    icon: Database,
    span: "col-span-2",
    visual: (
      <pre className="mt-5 overflow-hidden rounded-lg border border-rule bg-sunk px-3.5 py-3 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-dim">
        <span className="text-ink">UPDATE</span> collections SET amount = 2000{"\n"}
        <span className="text-ink">WHERE</span> receipt = &apos;RCT-BLR01-…-00412&apos;;{"\n"}
        <span className="text-st-rejected-fg">ERROR: RECORD_LOCKED · reconciled collection is immutable</span>
      </pre>
    ),
  },
  {
    condition: "Settlement late",
    outcome: "Flagged after 2 days",
    tint: "var(--st-delayed)",
    outcomeClass: "text-st-delayed-fg",
    icon: Clock3,
  },
  {
    condition: "Deposit bounced",
    outcome: "Cash back to the branch",
    tint: "var(--st-failed)",
    outcomeClass: "text-st-failed-fg",
    icon: RotateCcw,
    span: "col-span-2",
    visual: (
      <div className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[11px]">
        {[
          ["Deposited", "text-st-deposited-fg"],
          ["Failed", "text-st-failed-fg"],
          ["At branch", "text-st-received-fg"],
          ["Redeposited", "text-st-deposited-fg"],
        ].map(([label, tone], index) => (
          <span key={label} className="flex items-center gap-2">
            {index > 0 && <span className="text-rule-strong">→</span>}
            <span className={cn("rounded-md border border-rule bg-sunk px-2 py-1 whitespace-nowrap", tone)}>{label}</span>
          </span>
        ))}
      </div>
    ),
  },
  {
    condition: "UPI webhook delivered twice",
    outcome: "Counted once",
    tint: "var(--st-upi)",
    outcomeClass: "text-st-upi-fg",
    icon: Webhook,
  },
  {
    condition: "Receipt keyed by mistake",
    outcome: "Voided, never deleted",
    tint: "var(--st-voided)",
    outcomeClass: "text-st-voided-fg",
    icon: Ban,
  },
];

/** The business cases as condition → outcome, each one a rule the system enforces. */
export function CasesBento() {
  return (
    <div className="stagger grid-ruled mt-14 grid-flow-row-dense grid-cols-2 lg:grid-cols-4">
      {CASES.map((item) => {
        const Icon = item.icon;
        return (
          <Spotlight key={item.condition} tint={item.tint} className={cn("bg-raised", item.span)}>
            <div className="flex h-full flex-col p-4 sm:p-6">
              <span className="absolute inset-x-0 top-0 h-[2px] opacity-40 transition-opacity duration-300 group-hover/spot:opacity-100" style={{ background: item.tint }} />
              <Icon className="size-5 text-faint" strokeWidth={1.5} />
              <p className="mt-4 font-mono text-[11px] text-dim sm:mt-5 sm:text-[11.5px]">{item.condition}</p>
              <p className={cn("mt-1.5 font-display text-[19px] leading-tight max-sm:text-balance sm:text-[22px] tracking-[-0.015em]", item.outcomeClass)}>{item.outcome}</p>
              {item.visual}
            </div>
          </Spotlight>
        );
      })}
    </div>
  );
}
