"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const MAX_PULL_PX = 6;

/**
 * Pulls its child gently toward the pointer (at most 6px) and springs back on leave. Hover
 * devices only; inert under reduced motion. Wrap the primary CTA, not every button.
 *
 *   <Magnetic><Button asChild><Link href="/login">Open the demo</Link></Button></Magnetic>
 */
export function Magnetic({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

    const clamp = (value: number) => Math.max(-MAX_PULL_PX, Math.min(MAX_PULL_PX, value));
    const move = (event: PointerEvent) => {
      const rect = element.getBoundingClientRect();
      const x = (event.clientX - (rect.left + rect.width / 2)) * 0.22;
      const y = (event.clientY - (rect.top + rect.height / 2)) * 0.3;
      element.style.transform = `translate3d(${clamp(x)}px, ${clamp(y)}px, 0)`;
    };
    const leave = () => {
      element.style.transform = "";
    };

    element.addEventListener("pointermove", move);
    element.addEventListener("pointerleave", leave);
    return () => {
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerleave", leave);
    };
  }, []);

  return (
    <span
      ref={ref}
      className={cn("inline-flex transition-transform duration-300 ease-[var(--ease-spring)]", className)}
    >
      {children}
    </span>
  );
}
