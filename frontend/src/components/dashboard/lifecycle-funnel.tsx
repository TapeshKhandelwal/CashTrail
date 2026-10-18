import { Money } from "@/components/money/money";
import { formatCount, countOf } from "@/lib/format";
import { moneyRatio } from "@/lib/money";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Lifecycle } from "@/types/domain";

const STAGE_TONE: Record<string, StatusTone> = {
  COLLECTED: "collected",
  BRANCH_RECEIVED: "received",
  DEPOSITED: "deposited",
  SETTLED: "settled",
};

/**
 * How far this period's money has travelled: each stage as a bar against what was collected,
 * with expected dues as the reference line above.
 */
export function LifecycleFunnel({ lifecycle }: { lifecycle: Lifecycle }) {
  const collected = lifecycle.stages[0]?.amount ?? "0.00";

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-baseline justify-between gap-3 border-b border-dashed border-rule pb-3">
        <span className="eyebrow">Expected</span>
        <span className="text-[13px] text-dim">
          <Money value={lifecycle.expected.amount} whole className="text-ink" /> · {countOf(lifecycle.expected.count, "due")}
        </span>
      </div>
      <ol className="rows-enter flex flex-col gap-4">
        {lifecycle.stages.map((stage) => {
          const tone = TONE_CLASSES[STAGE_TONE[stage.stage] ?? "expected"];
          const ratio = moneyRatio(stage.amount, collected);
          return (
            <li key={stage.stage} className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-3">
                <span className="flex items-center gap-2 text-[13px] text-ink">
                  <span aria-hidden className={cn("size-1.5 rounded-full", tone.dot)} />
                  {stage.label}
                </span>
                <span className="text-[13px] tabular-nums">
                  <Money value={stage.amount} whole />
                  <span className="ml-2 font-mono text-[11px] text-faint">{formatCount(stage.count)}</span>
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-sunk" aria-hidden>
                <div
                  className={cn("h-full rounded-full transition-[width] duration-700 ease-out-quint", tone.dot)}
                  style={{ width: `${Math.max(ratio * 100, stage.count > 0 ? 2 : 0)}%` }}
                />
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
