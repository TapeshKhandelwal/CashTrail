import type { Metadata } from "next";

import { Logo } from "@/components/brand/logo";
import { RetryButton } from "@/components/pwa/retry-button";

export const metadata: Metadata = { title: "Offline", robots: { index: false } };

/** Precached by the service worker; must stay fully static (no data, no session). */
export default function OfflinePage() {
  return (
    <main className="flex min-h-dvh flex-col bg-paper px-6 pt-safe pb-safe">
      <header className="mx-auto flex h-16 w-full max-w-md items-center">
        <Logo size="sm" />
      </header>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center pb-24">
        <p className="flex items-center gap-2">
          <span aria-hidden className="size-1.5 rounded-full bg-st-collected" />
          <span className="eyebrow text-st-collected-fg">No connection</span>
        </p>
        <h1 className="mt-4 font-display text-[40px] leading-[1.05] text-ink">You&apos;re offline</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-dim">
          CashTrail needs a connection to record or load data. Your entries are safe on the server.
        </p>
        <div className="mt-8">
          <RetryButton />
        </div>
      </div>
    </main>
  );
}
