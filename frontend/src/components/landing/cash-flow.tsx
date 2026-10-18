import { Building2, HandCoins, Landmark, UserRound, Wallet } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const NODES: { label: string; detail: string; icon: LucideIcon; tone: StatusTone; record: string }[] = [
  { label: "Customer", detail: "Pays the EMI at home", icon: UserRound, tone: "expected", record: "Instalment due" },
  { label: "Agent", detail: "Issues a numbered receipt", icon: HandCoins, tone: "collected", record: "RCT-…-00412" },
  { label: "Branch", detail: "Counts every note", icon: Building2, tone: "received", record: "SUB-…-005" },
  { label: "Bank", detail: "Deposit slip recorded", icon: Landmark, tone: "deposited", record: "DEP-…-001" },
  { label: "Company account", detail: "Matched to the statement", icon: Wallet, tone: "settled", record: "Settled · locked" },
];

/**
 * Customer → agent → branch → bank → account, with a rupee pulse travelling each hand-off.
 * SVG + CSS offset-path, so it costs nothing on the main thread and stops under reduced motion.
 */
export function CashFlow() {
  return (
    <div className="relative mx-auto w-full max-w-6xl">
      <ol className="stagger relative grid gap-3 md:grid-cols-5 md:gap-0">
        {NODES.map((node, index) => {
          const tone = TONE_CLASSES[node.tone];
          const Icon = node.icon;
          return (
            <li key={node.label} className="relative flex md:flex-col md:items-center">
              {index < NODES.length - 1 && <Beam index={index} />}
              <div className="relative z-10 flex w-full items-center gap-4 rounded-2xl border border-rule bg-raised p-4 shadow-[0_1px_0_rgb(18_20_23/0.03)] md:mx-2 md:flex-col md:items-start md:gap-5 md:p-5">
                <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl border", tone.wash, "border-current/10", tone.text)}>
                  <Icon className="size-5" strokeWidth={1.6} />
                </span>
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="font-mono text-[10px] tracking-[0.16em] text-faint uppercase">Step {index + 1}</span>
                  <span className="text-[15px] font-medium text-ink">{node.label}</span>
                  <span className="text-[13px] leading-snug text-dim">{node.detail}</span>
                  <span className={cn("mt-1 inline-flex w-fit items-center gap-1.5 font-mono text-[11px]", tone.text)}>
                    <span className={cn("size-1.5 rounded-full", tone.dot)} />
                    {node.record}
                  </span>
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** The connector to the next node: a hairline with a coin of light running along it. */
function Beam({ index }: { index: number }) {
  return (
    <span aria-hidden className="pointer-events-none absolute z-0 max-md:top-full max-md:left-[37px] max-md:h-3 max-md:w-px md:top-[46px] md:left-1/2 md:h-px md:w-full">
      <span className="absolute inset-0 bg-rule-strong" />
      <span
        className="cash-pulse absolute size-2 rounded-full bg-brand shadow-[0_0_0_4px_color-mix(in_oklab,var(--brand)_18%,transparent)]"
        style={{ animationDelay: `${index * 0.55}s` }}
      />
    </span>
  );
}
