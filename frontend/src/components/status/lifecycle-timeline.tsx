import type { ReactNode } from "react";

import { formatDateTime } from "@/lib/dates";
import { CASH_LIFECYCLE, collectionStatus, TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { PaymentMode, TimelineStep } from "@/types/domain";

export type TimelineItemState = "done" | "current" | "pending" | "skipped";

export interface TimelineItem {
  id: string;
  label: string;
  tone: StatusTone;
  state: TimelineItemState;
  at?: string | null;
  /** Receipt / submission / deposit number or UTR, set in mono. */
  reference?: string | null;
  /** Secondary line: who acted, or "Not applicable for UPI". */
  note?: ReactNode;
}

/** Turns a receipt's `timeline` into display items; UPI marks the cash hand-offs as skipped. */
export function collectionTimelineItems(steps: TimelineStep[], mode: PaymentMode): TimelineItem[] {
  const byStatus = new Map(steps.map((step) => [step.status, step]));
  const lastReached = [...steps].reverse().find((step) => step.reached)?.status;
  const sequence = steps.some((step) => step.status === "VOIDED") ? steps.map((step) => step.status) : CASH_LIFECYCLE;

  return sequence.map((status) => {
    const meta = collectionStatus(status);
    const step = byStatus.get(status);
    if (!step) {
      return {
        id: status,
        label: meta.label,
        tone: meta.tone,
        state: "skipped",
        note: mode === "UPI" ? "Not applicable for UPI" : null,
      };
    }
    return {
      id: status,
      label: meta.label,
      tone: meta.tone,
      state: step.reached ? (status === lastReached ? "current" : "done") : "pending",
      at: step.at,
      reference: step.reference,
    };
  });
}

const STATE_TEXT: Record<TimelineItemState, string> = {
  done: "done",
  current: "current stage",
  pending: "not yet",
  skipped: "skipped",
};

/**
 * Vertical lifecycle in the ledger style: a hairline spine, a dot per stage in its status
 * colour, mono times and references. Reached stages are filled, the current one is ringed,
 * pending ones hollow, skipped ones dashed and struck through.
 *
 *   <LifecycleTimeline items={collectionTimelineItems(receipt.timeline, receipt.mode)} />
 */
export function LifecycleTimeline({ items, className }: { items: TimelineItem[]; className?: string }) {
  return (
    <ol className={cn("relative flex flex-col", className)}>
      {items.map((item, index) => {
        const tone = TONE_CLASSES[item.tone];
        const reached = item.state === "done" || item.state === "current";
        const last = index === items.length - 1;
        const nextReached = !last && ["done", "current"].includes(items[index + 1].state);
        return (
          <li key={item.id} className="relative flex gap-3.5 pb-5 last:pb-0">
            {!last && (
              <span
                aria-hidden
                className={cn(
                  "absolute top-4 bottom-0 left-[5px] w-px",
                  nextReached ? "bg-ink/25" : "bg-[repeating-linear-gradient(to_bottom,var(--rule-strong)_0_3px,transparent_3px_6px)]",
                )}
              />
            )}
            <span aria-hidden className="relative mt-1 flex size-[11px] shrink-0 items-center justify-center">
              {item.state === "current" && <span className={cn("absolute inset-[-4px] rounded-full opacity-20", tone.dot)} />}
              <span
                className={cn(
                  "size-[11px] rounded-full border-[1.5px]",
                  reached && cn(tone.dot, "border-transparent"),
                  item.state === "pending" && "border-rule-strong bg-raised",
                  item.state === "skipped" && "border-dashed border-rule-strong bg-raised",
                )}
              />
            </span>
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span
                  className={cn(
                    "text-[13.5px]",
                    reached ? "font-medium text-ink" : "text-dim",
                    item.state === "skipped" && "text-faint line-through decoration-rule-strong",
                  )}
                >
                  {item.label}
                  <span className="sr-only">, {STATE_TEXT[item.state]}</span>
                </span>
                {item.at && (
                  <time dateTime={item.at} className="font-mono text-[11px] text-faint tabular-nums">
                    {formatDateTime(item.at)}
                  </time>
                )}
              </div>
              {item.reference && <span className="font-mono text-[11.5px] tracking-[0.02em] wrap-anywhere text-dim">{item.reference}</span>}
              {item.note && <span className="text-[12.5px] text-faint">{item.note}</span>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
