import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Mono eyebrow, serif statement, dim lead: the opening of every landing section. */
export function SectionHeading({
  eyebrow,
  title,
  lead,
  center = false,
  className,
}: {
  eyebrow: string;
  title: ReactNode;
  lead?: ReactNode;
  center?: boolean;
  className?: string;
}) {
  return (
    <div data-anchor className={cn("reveal max-w-2xl", center && "mx-auto text-center", className)}>
      <p className="font-mono text-[11px] tracking-[0.16em] text-st-collected-fg uppercase">{eyebrow}</p>
      <h2 className="mt-4 font-display text-[clamp(2.1rem,4.5vw,3.4rem)] leading-[1.04] tracking-[-0.025em] text-balance text-ink">
        {title}
      </h2>
      {lead && <p className="mt-4 text-[17px] leading-relaxed text-pretty text-dim">{lead}</p>}
    </div>
  );
}
