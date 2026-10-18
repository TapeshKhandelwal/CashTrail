"use client";

import { Toaster } from "@/components/ui/sonner";
import { useIsMobile } from "@/hooks/use-mobile";

/** Clears the agent tab bar or a sticky action bar (see --bottom-bar-height in globals.css). */
const PHONE_BOTTOM = "calc(env(safe-area-inset-bottom) + var(--bottom-bar-height, 0px) + 0.75rem)";

/** Bottom-centre on phones, above whatever bar is pinned there; bottom-right on desktop. */
export function AppToaster() {
  const isMobile = useIsMobile();
  return (
    <Toaster
      position={isMobile ? "bottom-center" : "bottom-right"}
      closeButton
      duration={4_000}
      offset={isMobile ? { bottom: PHONE_BOTTOM } : undefined}
      mobileOffset={{ bottom: PHONE_BOTTOM, left: "1rem", right: "1rem" }}
    />
  );
}
