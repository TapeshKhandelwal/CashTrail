"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { toast } from "sonner";

import { SESSION_EXPIRED_EVENT } from "@/lib/api/client";
import { clearRuntimeCaches } from "@/lib/pwa";

/** When the API reports the session is gone, clear cached data and go to sign-in, keeping the page. */
export function SessionExpiryWatcher() {
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    const onExpired = () => {
      clearRuntimeCaches();
      queryClient.clear();
      toast.info("Your session ended. Sign in again to continue.", { id: "session-expired" });
      const next = `${window.location.pathname}${window.location.search}`;
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [queryClient, router]);

  return null;
}
