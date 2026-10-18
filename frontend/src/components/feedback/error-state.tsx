"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { errorMessage, isApiError } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  error: unknown;
  /** Query `refetch` or error boundary `reset`. */
  onRetry?: () => void;
  title?: string;
  /** Adds a "Go to dashboard" link. */
  homeHref?: string;
  compact?: boolean;
  bordered?: boolean;
  className?: string;
}

/** "We couldn't load this." with the API message in plain English, retry, and the request id in mono. */
export function ErrorState({
  error,
  onRetry,
  title = "We couldn't load this.",
  homeHref,
  compact = false,
  bordered = false,
  className,
}: ErrorStateProps) {
  const requestId = isApiError(error) ? error.requestId : null;
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-4 px-5 text-center sm:px-6",
        compact ? "py-10" : "py-12 sm:py-16 md:py-20",
        bordered && "rounded-xl border border-rule bg-raised",
        className,
      )}
    >
      <span aria-hidden className="flex items-center gap-2">
        <span className="size-1.5 rounded-full bg-st-rejected" />
        <span className="eyebrow text-st-rejected-fg">Not loaded</span>
      </span>
      <div className="flex max-w-sm flex-col gap-1.5">
        <p className={cn("font-display text-ink", compact ? "text-[19px]" : "text-[22px]")}>{title}</p>
        <p className="text-[13.5px] leading-relaxed text-dim">{errorMessage(error)}</p>
      </div>
      {(onRetry || homeHref) && (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {onRetry && (
            <Button variant="outline" onClick={onRetry}>
              <RotateCcw data-icon="inline-start" />
              Try again
            </Button>
          )}
          {homeHref && (
            <Button variant="ghost" asChild>
              <Link href={homeHref}>Go to dashboard</Link>
            </Button>
          )}
        </div>
      )}
      {requestId && <p className="font-mono text-[11px] tracking-[0.04em] wrap-anywhere text-faint">Request {requestId}</p>}
    </div>
  );
}
