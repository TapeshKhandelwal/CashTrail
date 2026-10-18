"use client";

import { useRef, type CSSProperties, type PointerEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface SpotlightProps {
  children: ReactNode;
  /** CSS colour of the wash, usually a status token: "var(--st-settled)". */
  tint?: string;
  /** Wash radius in px. */
  size?: number;
  className?: string;
}

/**
 * A soft radial wash of `tint` follows the pointer across the card. Two custom properties, no
 * re-renders. Children sit above the wash; inside, `group-hover/spot:` styles react to hover.
 */
export function Spotlight({ children, tint = "var(--brand)", size = 380, className }: SpotlightProps) {
  const ref = useRef<HTMLDivElement>(null);

  const track = (event: PointerEvent<HTMLDivElement>) => {
    const element = ref.current;
    if (!element || event.pointerType !== "mouse") return;
    const rect = element.getBoundingClientRect();
    element.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
    element.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
  };

  return (
    <div ref={ref} onPointerMove={track} className={cn("group/spot relative isolate overflow-hidden", className)}>
      <span
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
        style={
          {
            background: `radial-gradient(${size}px circle at var(--spot-x, 50%) var(--spot-y, 50%), color-mix(in oklab, ${tint} 9%, transparent), transparent 65%)`,
          } as CSSProperties
        }
      />
      {children}
    </div>
  );
}
