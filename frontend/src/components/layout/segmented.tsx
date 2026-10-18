"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
  /** Mono count after the label, e.g. overdue visits. */
  count?: number;
}

interface SegmentedProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: readonly SegmentOption<T>[];
  /** Names the control for assistive tech: "Visits", "Mode", "Range". */
  label: string;
  size?: "sm" | "md";
  /** Stretch segments to fill the row (phones, forms). */
  block?: boolean;
  className?: string;
}

/**
 * Segmented control: Due today · Overdue · All, Cash | UPI, 7d · 14d · 30d. A radiogroup with
 * arrow-key navigation. Pair with nuqs `useQueryState` when the choice belongs in the URL.
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
  block = false,
  className,
}: SegmentedProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (index + step + options.length) % options.length;
    onChange(options[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "inline-flex items-center rounded-lg border border-rule bg-sunk p-0.5 max-sm:max-w-full max-sm:scrollbar-none max-sm:overflow-x-auto",
        block && "flex w-full",
        className,
      )}
    >
      {options.map((option, index) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[index] = node;
            }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "hit-area relative inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-[color,background-color,box-shadow] duration-150 outline-none focus-visible:ring-2 focus-visible:ring-focus",
              size === "sm" ? "h-7 px-2.5 text-[12.5px]" : "h-8 px-3 text-[13px] max-sm:h-9",
              block && "flex-1",
              active ? "bg-raised text-ink shadow-lift" : "text-dim hover:text-ink",
            )}
          >
            {option.label}
            {option.count !== undefined && (
              <span className={cn("font-mono text-[11px] tabular-nums", active ? "text-dim" : "text-faint")}>{option.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
