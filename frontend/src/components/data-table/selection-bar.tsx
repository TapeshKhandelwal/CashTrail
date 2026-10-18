"use client";

import { X } from "lucide-react";
import { AnimatePresence, m } from "motion/react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { transition } from "@/lib/motion";

/** Floating bar for bulk actions: "3 selected · ₹1,42,000" plus actions. */
export function SelectionBar({
  count,
  summary,
  actions,
  onClear,
}: {
  count: number;
  summary?: ReactNode;
  actions?: ReactNode;
  onClear: () => void;
}) {
  return (
    <AnimatePresence>
      {count > 0 && (
        <m.div
          role="region"
          aria-label="Selected rows"
          initial={{ y: "120%", opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: "120%", opacity: 0 }}
          transition={transition.sheet}
          className="fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+var(--bottom-bar-height,0px)+1rem)] z-40 mx-auto flex max-w-2xl flex-wrap items-center gap-3 rounded-xl border border-rule bg-raised px-4 py-3 shadow-float md:bottom-6"
        >
          <p className="text-[13.5px] text-ink tabular-nums" aria-live="polite">
            <span className="font-mono text-[11px] tracking-[0.12em] text-faint uppercase">{count} selected</span>
            {summary && <span className="ml-2 font-medium">{summary}</span>}
          </p>
          <div className="ml-auto flex items-center gap-2">
            {actions}
            <Button variant="ghost" size="icon-sm" onClick={onClear} aria-label="Clear selection">
              <X />
            </Button>
          </div>
        </m.div>
      )}
    </AnimatePresence>
  );
}
