import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  /** Mono label above the title: role or branch context, e.g. "BLR01 · Branch desk". */
  eyebrow?: ReactNode;
  title: ReactNode;
  /** One dim line. */
  description?: ReactNode;
  /** Page-level actions; they wrap under the title on phones. */
  actions?: ReactNode;
  /** Tabs, segmented filters or a summary strip under the title block. */
  children?: ReactNode;
  /** Hairline under the header. */
  divider?: boolean;
  className?: string;
}

/**
 * One per page and the page's only h1.
 *
 *   <PageHeader eyebrow="BLR01 · Reconciliation" title="Submissions"
 *     description="Cash handed over by agents, waiting to be counted." actions={<Button>…</Button>} />
 */
export function PageHeader({ eyebrow, title, description, actions, children, divider = false, className }: PageHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-5 pb-7 md:pb-8", divider && "mb-7 border-b border-rule md:mb-8", className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between sm:gap-8">
        <div className="flex min-w-0 flex-col">
          {eyebrow && <p className="eyebrow mb-2.5">{eyebrow}</p>}
          <h1 className="title-page text-balance wrap-break-word">{title}</h1>
          {description && <p className="mt-2 max-w-2xl text-[14.5px] leading-relaxed text-dim">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children}
    </header>
  );
}
