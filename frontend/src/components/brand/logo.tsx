import { cn } from "@/lib/utils";

import { LogoMark } from "./logo-mark";

type LogoSize = "sm" | "md" | "lg";

const SIZES: Record<LogoSize, { mark: string; word: string; gap: string }> = {
  sm: { mark: "size-[18px]", word: "text-[17px]", gap: "gap-1.5" },
  md: { mark: "size-[22px]", word: "text-[20px]", gap: "gap-2" },
  lg: { mark: "size-7", word: "text-[25px]", gap: "gap-2.5" },
};

interface LogoProps {
  size?: LogoSize;
  className?: string;
}

/** Mark and live-text wordmark, so the serif renders crisply at any size. */
export function Logo({ size = "md", className }: LogoProps) {
  const s = SIZES[size];
  return (
    <span className={cn("group/logo inline-flex items-center", s.gap, className)}>
      <LogoMark className={s.mark} />
      <Wordmark className={s.word} />
    </span>
  );
}

/** Logo with the mono descriptor beneath the wordmark (sidebar, receipts, footer). */
export function LogoLockup({ size = "md", className }: LogoProps) {
  const s = SIZES[size];
  return (
    <span className={cn("group/logo inline-flex items-center", s.gap, className)}>
      <LogoMark className={s.mark} />
      <span className="flex flex-col">
        <Wordmark className={s.word} />
        <span className="mt-0.5 font-mono text-[9px] leading-none tracking-[0.18em] text-faint uppercase">
          Cash reconciliation
        </span>
      </span>
    </span>
  );
}

function Wordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "font-display leading-none font-medium tracking-[-0.03em] whitespace-nowrap text-ink",
        className,
      )}
    >
      CashTrail
    </span>
  );
}
