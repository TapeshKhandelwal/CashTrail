import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface RecordCardProps {
  /** The record's name or reference. */
  title: ReactNode;
  /** Render the title as a mono reference (RCT-…, SUB-…, DEP-…). */
  mono?: boolean;
  /** One dim line under the title: who or what it belongs to. */
  subtitle?: ReactNode;
  amount?: ReactNode;
  /** Status, right-aligned beside the subtitle (it wraps under it when long). */
  badge?: ReactNode;
  /** Faint facts on the last line, separated by a dot; empty values are skipped. */
  meta?: ReactNode[];
}

/**
 * Compact phone card for a list row: reference and amount, then owner and status, then a line
 * of faint facts. Used as a `DataTable` `renderCard`.
 */
export function RecordCard({ title, mono = false, subtitle, amount, badge, meta = [] }: RecordCardProps) {
  const facts = meta.filter((item) => item !== null && item !== undefined && item !== false && item !== "");
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-start justify-between gap-3">
        <span className={cn("min-w-0 text-[14.5px] font-medium text-ink wrap-anywhere", mono && "font-mono text-[12.5px] leading-5 font-normal tracking-[0.01em]")}>
          {title}
        </span>
        {amount && <span className="shrink-0 text-right text-[15px] leading-5 font-medium text-ink tabular-nums">{amount}</span>}
      </div>
      {(subtitle || badge) && (
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          {subtitle && <span className="min-w-0 text-[13px] text-dim wrap-break-word">{subtitle}</span>}
          {badge && <span className="ml-auto shrink-0">{badge}</span>}
        </div>
      )}
      {facts.length > 0 && (
        <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[12px] text-faint">
          {facts.map((item, index) => (
            <Fragment key={index}>
              {index > 0 && <span aria-hidden>·</span>}
              <span className="inline-flex min-w-0 items-center wrap-anywhere">{item}</span>
            </Fragment>
          ))}
        </p>
      )}
    </div>
  );
}
