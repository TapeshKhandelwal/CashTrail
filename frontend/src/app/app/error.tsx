"use client";

import { ErrorState } from "@/components/feedback/error-state";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex flex-col gap-2">
      <ErrorState error={error} onRetry={reset} homeHref="/app" bordered />
      {error.digest && <p className="text-center font-mono text-[11px] text-faint">Reference {error.digest}</p>}
    </div>
  );
}
