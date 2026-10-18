import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/utils";

interface RevealLinesProps {
  /** One entry per line: the break points are a typographic decision, not the viewport's. */
  lines: ReactNode[];
  /** Seconds before the first line starts. */
  delay?: number;
  /** Seconds between lines. */
  step?: number;
  className?: string;
}

/**
 * Masked line reveal for headlines: each line rises out of its own overflow clip. Pure CSS, so
 * it runs on first paint without hydration and is off under reduced motion.
 *
 *   <h1 className="font-display …"><RevealLines lines={["Every rupee collected.", "Every rupee accounted for."]} /></h1>
 */
export function RevealLines({ lines, delay = 0, step = 0.09, className }: RevealLinesProps) {
  return (
    <span className={cn("block", className)}>
      {lines.map((line, index) => (
        // Padding plus negative margin leaves room for descenders inside the clip.
        <span key={index} className="-mb-[0.14em] block overflow-hidden pb-[0.14em]">
          <span
            className="line-rise block"
            style={{ "--line-delay": `${delay + index * step}s` } as CSSProperties}
          >
            {line}
          </span>
        </span>
      ))}
    </span>
  );
}
