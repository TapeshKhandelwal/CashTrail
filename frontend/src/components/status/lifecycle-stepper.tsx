import { CASH_LIFECYCLE, collectionStatus, TONE_CLASSES } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { CollectionStatus, PaymentMode } from "@/types/domain";

/**
 * Compact "where is the money" rail for rows and cards: five segments, filled in each stage's
 * colour up to the current one. UPI skips the three cash hand-offs (dashed).
 */
export function LifecycleProgress({
  status,
  mode = "CASH",
  className,
}: {
  status: CollectionStatus;
  mode?: PaymentMode;
  className?: string;
}) {
  if (status === "VOIDED") return null;
  const reachedIndex = CASH_LIFECYCLE.indexOf(status);
  return (
    <ol className={cn("flex items-center gap-0.5", className)} aria-label={`Lifecycle: ${collectionStatus(status).label}`}>
      {CASH_LIFECYCLE.map((stage, index) => {
        const skipped = mode === "UPI" && index > 0 && index < CASH_LIFECYCLE.length - 1;
        const reached = !skipped && index <= reachedIndex;
        return (
          <li
            key={stage}
            title={collectionStatus(stage).label}
            className={cn(
              "h-1 flex-1 rounded-full",
              reached ? TONE_CLASSES[collectionStatus(stage).tone].dot : "bg-rule",
              skipped && "bg-[repeating-linear-gradient(90deg,var(--rule-strong)_0_3px,transparent_3px_6px)]",
            )}
          />
        );
      })}
    </ol>
  );
}

/**
 * Step header for multi-step flows: mono numerals, the current step in ink, done steps ticked.
 *
 *   <FlowSteps steps={["Customer", "Amount", "Confirm"]} current={1} />
 */
export function FlowSteps({ steps, current, className }: { steps: string[]; current: number; className?: string }) {
  return (
    <ol className={cn("flex items-center gap-3", className)}>
      {steps.map((label, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li
            key={label}
            aria-current={active ? "step" : undefined}
            className="flex flex-1 items-center gap-3 last:flex-none"
          >
            <span
              className={cn(
                "flex items-center gap-2 font-mono text-[11px] tracking-[0.12em] uppercase transition-colors duration-200",
                active ? "text-ink" : done ? "text-dim" : "text-faint",
              )}
            >
              <span
                className={cn(
                  "flex size-5 items-center justify-center rounded-full border text-[10px] tracking-normal tabular-nums transition-colors duration-200",
                  active && "border-ink bg-ink text-paper",
                  done && "border-brand text-brand",
                  !active && !done && "border-rule-strong",
                )}
              >
                {done ? "✓" : index + 1}
              </span>
              <span className="max-sm:sr-only">{label}</span>
              <span className="sr-only">{done ? " (done)" : active ? " (current)" : ""}</span>
            </span>
            {index < steps.length - 1 && (
              <span aria-hidden className="relative h-px min-w-4 flex-1 bg-rule">
                <span
                  className={cn(
                    "absolute inset-0 origin-left bg-ink/40 transition-transform duration-300 ease-out-quint",
                    done ? "scale-x-100" : "scale-x-0",
                  )}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
