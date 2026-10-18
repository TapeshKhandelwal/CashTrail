"use client";

import { NumberFlowGroup } from "@number-flow/react";
import { ArrowUpRight, Info } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSyncExternalStore, type CSSProperties, type ReactNode } from "react";

import { AnimatedCount, AnimatedMoney } from "@/components/money/animated-money";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { formatCount, formatINR } from "@/lib/format";
import type { MoneyString } from "@/lib/money";
import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

const Sparkline = dynamic(() => import("./sparkline"), { ssr: false, loading: () => <div className="h-8" aria-hidden /> });

export interface KpiDelta {
  /** Display text, e.g. "12.5%" or "₹4,200". */
  value: string;
  direction: "up" | "down";
  /** Whether this direction is good news (for discrepancies, up is bad). */
  good: boolean;
  /** e.g. "vs last week". */
  label?: string;
}

interface KpiTileProps {
  /** Mono label. */
  label: string;
  /** A money value (rolls on change, whole rupees)… */
  amount?: MoneyString;
  /** …or a count. */
  count?: number;
  /** Dim context line under the value: "from 6 receipts", "oldest 2d". */
  context?: ReactNode;
  delta?: KpiDelta;
  /** A 2px rule in a status colour along the top edge: draws the eye to what needs action. */
  tone?: StatusTone;
  /** Explains how the number is worked out. */
  info?: string;
  /** Display-only recent values for a sparkline. */
  trend?: number[];
  /** Makes the whole tile a link (with a quiet arrow on hover). */
  href?: string;
  loading?: boolean;
  className?: string;
}

/** One cell of a <KpiGrid>. No icons in circles; the number is the hero. */
export function KpiTile({ label, amount, count, context, delta, tone, info, trend, href, loading = false, className }: KpiTileProps) {
  // Phones size the figure to its own length so "₹19,61,181" fits a two-up tile.
  const figureChars = amount !== undefined ? formatINR(amount, { whole: true }).length : formatCount(count ?? 0).length;
  const body = loading ? (
    <>
      <Skeleton className="h-2.5 w-24" />
      <Skeleton className="mt-1 h-8 w-36" />
      <Skeleton className="mt-auto h-3 w-28" />
    </>
  ) : (
    <>
      <div className="flex items-center gap-1.5">
        <h3 className="eyebrow">{label}</h3>
        {info && <InfoTip label={label} info={info} />}
        {href && (
          <ArrowUpRight
            aria-hidden
            className="ml-auto size-3.5 text-faint opacity-0 transition-[opacity,transform] duration-200 group-hover/kpi:translate-x-0.5 group-hover/kpi:-translate-y-0.5 group-hover/kpi:opacity-100"
          />
        )}
      </div>
      <div
        className="figure mt-1 max-sm:text-[length:clamp(1.125rem,calc(100cqi/(var(--figure-chars)*0.62)),1.75rem)]"
        style={{ "--figure-chars": Math.max(figureChars, 5) } as CSSProperties}
      >
        {amount !== undefined ? <AnimatedMoney value={amount} /> : <AnimatedCount value={count ?? 0} />}
      </div>
      {(context || delta) && (
        <div className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 pt-1 text-[12.5px] text-dim">
          {delta && <Delta delta={delta} />}
          {context}
        </div>
      )}
      {trend && trend.length > 1 && (
        <div className="-mx-1 mt-1">
          <Sparkline data={trend} />
        </div>
      )}
    </>
  );

  const classes = cn(
    "group/kpi @container relative flex min-h-[132px] min-w-0 flex-col gap-1.5 bg-raised p-5 max-sm:min-h-[116px] max-sm:p-4",
    tone && cn("border-t-2", TONE_CLASSES[tone].rule),
    href && "transition-colors hover:bg-sunk/60",
    className,
  );

  if (href && !loading) {
    return (
      <Link href={href} aria-label={label} className={cn(classes, "outline-none focus-visible:ring-3 focus-visible:ring-focus focus-visible:ring-inset")}>
        {body}
      </Link>
    );
  }
  return (
    <section aria-label={label} aria-busy={loading || undefined} className={classes}>
      {body}
    </section>
  );
}

/**
 * The (i) next to a label: a tooltip for mouse users, a popover a tap opens on touch screens.
 * The hit area is 40px around the 12px icon, without moving the label.
 */
function InfoTip({ label, info }: { label: string; info: string }) {
  const coarse = useCoarsePointer();
  const trigger = (
    <button
      type="button"
      className="relative z-10 rounded-full text-faint outline-none after:absolute after:top-1/2 after:left-1/2 after:size-10 after:-translate-1/2 hover:text-ink focus-visible:text-ink focus-visible:ring-2 focus-visible:ring-focus data-[state=open]:text-ink"
      aria-label={`About ${label}`}
    >
      <Info className="size-3" />
    </button>
  );
  if (coarse) {
    return (
      <Popover>
        <PopoverTrigger asChild>{trigger}</PopoverTrigger>
        <PopoverContent side="top" className="w-auto max-w-64 px-3 py-2 text-[12.5px] leading-snug">
          {info}
        </PopoverContent>
      </Popover>
    );
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>{trigger}</TooltipTrigger>
      <TooltipContent className="max-w-60">{info}</TooltipContent>
    </Tooltip>
  );
}

const COARSE = "(pointer: coarse)";

function useCoarsePointer(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(COARSE);
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia(COARSE).matches,
    () => false,
  );
}

function Delta({ delta }: { delta: KpiDelta }) {
  return (
    <span className={cn("font-medium tabular-nums", delta.good ? "text-st-settled-fg" : "text-st-short-fg")}>
      <span aria-hidden>{delta.direction === "up" ? "↑" : "↓"}</span>
      <span className="sr-only">{delta.direction === "up" ? "Up" : "Down"} </span>
      {delta.value}
      {delta.label && <span className="ml-1 font-normal text-faint">{delta.label}</span>}
    </span>
  );
}

/**
 * One ruled container of KPI tiles (a gap-px grid on the rule colour). Numbers roll together.
 * Pass as many tiles as `columns`. Two up on phones, with figures that shrink to fit the tile.
 *
 *   <KpiGrid columns={5}>
 *     <KpiTile label="Collected today" amount={s.collected_today} context="from 42 receipts" />
 *   </KpiGrid>
 */
export function KpiGrid({ children, columns = 4, className }: { children: ReactNode; columns?: 2 | 3 | 4 | 5; className?: string }) {
  return (
    <NumberFlowGroup>
      <div
        className={cn(
          "grid-ruled grid-cols-2",
          // An odd tile out on two columns spans the row rather than leaving a grey hole; only
          // while the grid is two-up, so the wide layout keeps every tile in one row.
          columns === 3 && "max-lg:[&>:last-child:nth-child(odd)]:col-span-2 lg:grid-cols-3",
          columns === 4 && "xl:grid-cols-4",
          columns === 5 && "max-xl:[&>:last-child:nth-child(odd)]:col-span-2 xl:grid-cols-5",
          className,
        )}
      >
        {children}
      </div>
    </NumberFlowGroup>
  );
}
