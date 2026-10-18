import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import { Illustration, type IllustrationName } from "./illustrations";

interface EmptyStateProps {
  /** Calm and factual: "No open discrepancies." */
  title: string;
  /** One dim sentence. */
  description?: ReactNode;
  illustration?: IllustrationName;
  /** At most one action (a Button or Link). */
  action?: ReactNode;
  /** Tighter spacing for cards, sheets and table bodies. */
  compact?: boolean;
  /** Draws its own card (use when not already inside one). */
  bordered?: boolean;
  className?: string;
}

/**
 *   <EmptyState illustration="settled" title="No open discrepancies." description="Every count and deposit is reconciled." />
 */
export function EmptyState({
  title,
  description,
  illustration = "ledger",
  action,
  compact = false,
  bordered = false,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center px-5 text-center sm:px-6",
        compact ? "gap-3 py-10" : "gap-4 py-12 sm:py-16 md:py-20",
        bordered && "rounded-xl border border-rule bg-raised",
        className,
      )}
    >
      <Illustration name={illustration} className={compact ? "h-12 w-18" : undefined} />
      <div className="flex max-w-sm flex-col gap-1.5">
        <p className={cn("font-display text-ink", compact ? "text-[19px]" : "text-[22px]")}>{title}</p>
        {description && <p className="text-[13.5px] leading-relaxed text-dim">{description}</p>}
      </div>
      {action && <div className="mt-1 flex flex-wrap items-center justify-center gap-2">{action}</div>}
    </div>
  );
}
