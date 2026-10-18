import { cn } from "@/lib/utils";

/**
 * The "recorded" moment: a brand tick that draws itself inside a hairline circle. Pair it with
 * the receipt sliding up (`animate-rise`); no confetti. Static under reduced motion.
 */
export function SuccessCheck({ size = 48, className, label = "Recorded" }: { size?: number; className?: string; label?: string }) {
  return (
    <span role="img" aria-label={label} className={cn("inline-flex text-brand", className)} style={{ width: size, height: size }}>
      <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" className="tick-draw size-full">
        <circle cx="24" cy="24" r="22.5" strokeWidth="1.25" className="opacity-35" />
        <path d="M15 24.5l6.5 6.5L33.5 18" strokeWidth="2.25" pathLength={1} />
      </svg>
    </span>
  );
}
