import type { ReactNode } from "react";

import { TONE_CLASSES, type StatusTone } from "@/lib/status";
import { cn } from "@/lib/utils";

interface SectionCardProps {
  eyebrow?: ReactNode;
  title?: ReactNode;
  description?: ReactNode;
  /** Right side of the header: a link ("View all →"), a segmented control. */
  actions?: ReactNode;
  /** Muted strip under the body: totals, a primary action. */
  footer?: ReactNode;
  /** A 2px status rule along the top edge. */
  tone?: StatusTone;
  /** Body without padding: tables and ruled lists that run edge to edge. */
  flush?: boolean;
  /** Render the header as h2 (default) or h3 when nested under another section. */
  headingLevel?: 2 | 3;
  id?: string;
  className?: string;
  children: ReactNode;
}

/**
 * The white card every grouped piece of content sits in: hairline border, 12px radius, no
 * shadow. Header and footer are separated by rules.
 *
 *   <SectionCard eyebrow="Cash ageing" title="Held by agents" actions={<Link …>All agents</Link>} flush>
 *     <ul className="divide-y divide-rule">…</ul>
 *   </SectionCard>
 */
export function SectionCard({
  eyebrow,
  title,
  description,
  actions,
  footer,
  tone,
  flush = false,
  headingLevel = 2,
  id,
  className,
  children,
}: SectionCardProps) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const hasHeader = Boolean(eyebrow || title || description || actions);
  return (
    <section
      id={id}
      className={cn(
        "flex min-w-0 flex-col overflow-hidden rounded-xl border border-rule bg-raised",
        tone && cn("border-t-2", TONE_CLASSES[tone].rule),
        className,
      )}
    >
      {hasHeader && (
        <header className={cn("flex flex-wrap items-start justify-between gap-3 px-5 pt-4.5", flush ? "border-b border-rule pb-4" : "pb-1")}>
          <div className="flex min-w-0 flex-col gap-1">
            {eyebrow && <p className="eyebrow">{eyebrow}</p>}
            {title && <Heading className="text-[15px] font-medium text-ink">{title}</Heading>}
            {description && <p className="text-[13px] text-dim">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("flex-1", !flush && "px-5 pt-3 pb-5", !flush && !hasHeader && "pt-5")}>{children}</div>
      {footer && <footer className="border-t border-rule bg-sunk/60 px-5 py-3">{footer}</footer>}
    </section>
  );
}

/**
 * Label/value pairs in a ruled grid (detail pages, drawers).
 *
 *   <FactList items={[["Loan", <span className="font-mono">LN-…</span>], ["Outstanding", <Money … />]]} />
 */
export function FactList({ items, columns = 2, className }: { items: [label: ReactNode, value: ReactNode][]; columns?: 1 | 2 | 3; className?: string }) {
  return (
    <dl
      className={cn(
        "grid-ruled",
        columns === 1 && "grid-cols-1",
        columns === 2 && "grid-cols-1 sm:grid-cols-2",
        columns === 3 && "grid-cols-1 sm:grid-cols-3",
        items.length % columns !== 0 && columns > 1 && "sm:[&>:last-child]:col-span-full",
        className,
      )}
    >
      {items.map(([label, value], index) => (
        <div key={index} className="flex min-w-0 flex-col gap-1 px-4 py-3">
          <dt className="eyebrow">{label}</dt>
          <dd className="min-w-0 text-[14px] text-ink max-sm:wrap-anywhere sm:wrap-break-word">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
