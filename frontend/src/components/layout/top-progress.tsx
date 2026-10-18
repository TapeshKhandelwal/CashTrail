"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/** A brand hairline that sweeps while data loads; waits 200ms so quick fetches never flicker. */
export function TopProgress() {
  const busy = useIsFetching() + useIsMutating() > 0;
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(busy), busy ? 200 : 120);
    return () => clearTimeout(timer);
  }, [busy]);

  return (
    <div
      role="progressbar"
      aria-label="Loading"
      aria-hidden={!visible}
      data-print="hide"
      className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden transition-opacity duration-300"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {visible && <div className="h-full w-full origin-left animate-[top-progress_1.2s_var(--ease-out-quint)_infinite] bg-brand" />}
    </div>
  );
}
