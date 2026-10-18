"use client";

import { useSerwist } from "@serwist/turbopack/react";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

/**
 * A new deploy is waiting: ask before activating it, so a half-filled collection form is never
 * reloaded from under the agent. Reloads only after the user taps Update.
 */
export function SwUpdateToast() {
  const { serwist } = useSerwist();
  const accepted = useRef(false);

  useEffect(() => {
    if (!serwist) return;
    const onWaiting = () =>
      toast("A new version of CashTrail is ready.", {
        id: "sw-update",
        duration: Infinity,
        action: {
          label: "Update",
          onClick: () => {
            accepted.current = true;
            serwist.messageSkipWaiting();
          },
        },
      });
    // `controlling` also fires on first install (clientsClaim); reload only when asked.
    const onControlling = () => {
      if (accepted.current) window.location.reload();
    };
    serwist.addEventListener("waiting", onWaiting);
    serwist.addEventListener("controlling", onControlling);
    return () => {
      serwist.removeEventListener("waiting", onWaiting);
      serwist.removeEventListener("controlling", onControlling);
    };
  }, [serwist]);

  return null;
}
