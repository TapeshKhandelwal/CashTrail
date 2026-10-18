import { cookies } from "next/headers";
import { Suspense, type ReactNode } from "react";

import { ShellFallback } from "@/components/layout/shell-fallback";
import { AppShell } from "@/components/layout/app-shell";
import { MotionProvider } from "@/components/providers/motion-provider";
import { SessionProvider } from "@/components/providers/session-provider";
import { requireSession } from "@/lib/auth/session";

/** The session is request-time data, so the whole shell streams in behind this boundary. */
export default function AuthenticatedLayout({ children }: LayoutProps<"/app">) {
  return (
    <Suspense fallback={<ShellFallback />}>
      <SessionShell>{children}</SessionShell>
    </Suspense>
  );
}

async function SessionShell({ children }: { children: ReactNode }) {
  const [{ user }, store] = await Promise.all([requireSession(), cookies()]);
  const sidebarOpen = store.get("sidebar_state")?.value !== "false";
  return (
    <SessionProvider user={user}>
      <MotionProvider>
        <AppShell defaultSidebarOpen={sidebarOpen}>{children}</AppShell>
      </MotionProvider>
    </SessionProvider>
  );
}
