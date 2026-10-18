"use client";

import { useEffect, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const SWAP_MS = 380;

interface TickerProps {
  items: readonly ReactNode[];
  /** Milliseconds each item stays on screen. */
  interval?: number;
  className?: string;
}

/**
 * One mono line that cycles through `items`, the outgoing line lifting away before the next
 * arrives. Holds the first item under reduced motion. Hidden from assistive tech: pass the same
 * facts elsewhere in readable form if they matter.
 */
export function Ticker({ items, interval = 3400, className }: TickerProps) {
  const [index, setIndex] = useState(0);
  const [shown, setShown] = useState(true);

  useEffect(() => {
    if (items.length < 2 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let swap: ReturnType<typeof setTimeout>;
    const cycle = setInterval(() => {
      setShown(false);
      swap = setTimeout(() => {
        setIndex((current) => (current + 1) % items.length);
        setShown(true);
      }, SWAP_MS);
    }, interval);
    return () => {
      clearInterval(cycle);
      clearTimeout(swap);
    };
  }, [items.length, interval]);

  return (
    <span aria-hidden className={cn("inline-flex h-5 min-w-0 items-center overflow-hidden align-middle", className)}>
      <span
        className={cn(
          "block truncate font-mono text-[11px] tracking-[0.12em] text-dim uppercase transition-[transform,opacity] duration-[380ms] ease-out-quint",
          shown ? "translate-y-0 opacity-100" : "-translate-y-full opacity-0",
        )}
      >
        {items[index]}
      </span>
    </span>
  );
}
