"use client";

import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/*
 * Layout-matched placeholders on --sunk with a slow shimmer. Heights equal the loaded
 * components so nothing shifts when data arrives.
 */

export function PageHeaderSkeleton({ actions = false }: { actions?: boolean }) {
  return (
    <div className="flex flex-col gap-4 pb-7 sm:flex-row sm:items-end sm:justify-between md:pb-8" aria-hidden>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-2.5 w-28" />
        <Skeleton className="h-8 w-60 max-w-full" />
        <Skeleton className="h-3.5 w-80 max-w-full" />
      </div>
      {actions && <Skeleton className="h-9 w-32" />}
    </div>
  );
}

/** Matches <KpiGrid>: one ruled container of tiles. */
export function KpiGridSkeleton({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid-ruled grid-cols-2 xl:grid-cols-4", className)} aria-hidden>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex h-[132px] min-w-0 flex-col gap-3 p-5 max-sm:h-[116px] max-sm:p-4">
          <Skeleton className="h-2.5 w-24 max-w-full" />
          <Skeleton className="h-8 w-36 max-w-full" />
          <Skeleton className="mt-auto h-3 w-28 max-w-full" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({ rows = 8, columns = 5, className }: { rows?: number; columns?: number; className?: string }) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-rule bg-raised", className)} aria-hidden>
      <div className="flex h-10 items-center gap-6 border-b border-rule bg-sunk px-4">
        {Array.from({ length: columns }, (_, index) => (
          <Skeleton key={index} className="h-2.5 flex-1 bg-rule/70" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="flex h-11 items-center gap-6 border-b border-rule px-4 last:border-b-0">
          {Array.from({ length: columns }, (_, column) => (
            <Skeleton key={column} className={cn("h-3 flex-1", column === columns - 1 && "max-w-20")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function CardListSkeleton({ count = 5, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("overflow-hidden rounded-xl border border-rule bg-raised", className)} aria-hidden>
      {Array.from({ length: count }, (_, index) => (
        <div key={index} className="flex h-[72px] items-center gap-3 border-b border-rule px-4 last:border-b-0">
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-2.5 w-3/5" />
          </div>
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

export function ChartSkeleton({ height = 260, className }: { height?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-5 rounded-xl border border-rule bg-raised p-4 sm:p-5", className)} aria-hidden>
      <div className="flex flex-col gap-2">
        <Skeleton className="h-2.5 w-24" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Skeleton className="w-full" style={{ height }} />
    </div>
  );
}

export function DetailSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-4", className)} aria-hidden>
      <Skeleton className="h-36 w-full rounded-xl" />
      <div className="grid-ruled grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="flex h-16 flex-col justify-center gap-2 px-4">
            <Skeleton className="h-2.5 w-16" />
            <Skeleton className="h-3.5 w-24" />
          </div>
        ))}
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}

/** A "Still loading…" line with retry, shown only if a load runs past `afterMs`. */
export function StillLoading({ onRetry, afterMs = 10_000 }: { onRetry?: () => void; afterMs?: number }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), afterMs);
    return () => clearTimeout(timer);
  }, [afterMs]);
  if (!visible) return null;
  return (
    <p role="status" className="py-3 text-center text-[12.5px] text-dim">
      Still loading…{" "}
      {onRetry && (
        <button type="button" onClick={onRetry} className="font-medium text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink">
          Retry
        </button>
      )}
    </p>
  );
}
