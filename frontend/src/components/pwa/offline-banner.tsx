"use client";

import { WifiOff } from "lucide-react";
import { AnimatePresence, m } from "motion/react";
import { useOffline } from "next/offline";

/** Shown under the top bar while offline; money-moving buttons check `useOffline()` too. */
export function OfflineBanner() {
  const offline = useOffline();
  return (
    <AnimatePresence initial={false}>
      {offline && (
        <m.div
          role="status"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="overflow-hidden border-b border-st-collected/25 bg-st-collected/8 text-st-collected-fg"
        >
          <p className="flex items-center justify-center gap-2 px-4 py-2 text-[13px] font-medium">
            <WifiOff className="size-4 shrink-0" aria-hidden />
            You&apos;re offline. Nothing is recorded until you reconnect.
          </p>
        </m.div>
      )}
    </AnimatePresence>
  );
}
