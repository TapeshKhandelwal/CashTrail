import { cn } from "@/lib/utils";

/** The receipt, with the slot its total line runs through. Shared with the icon generator. */
export const MARK_BODY_PATH =
  "M7 3H17A4 4 0 0 1 21 7V14H9.5A1.5 1.5 0 0 0 9.5 17H21A4 4 0 0 1 17 21H7A4 4 0 0 1 3 17V7A4 4 0 0 1 7 3Z";
/** The trail: the total line leaving the receipt and turning toward the bank. */
export const MARK_TRAIL_PATH = "M21 14H23A6.5 6.5 0 0 1 29.5 20.5V27.5A1.5 1.5 0 0 1 26.5 27.5V20.5A3.5 3.5 0 0 0 23 17H21Z";

interface LogoMarkProps {
  className?: string;
  /** Accessible name; omit when the mark sits beside the wordmark. */
  title?: string;
}

/**
 * Flat, one colour (currentColor, brand by default). Inside a `group/logo` the trail retracts
 * and redraws on hover.
 */
export function LogoMark({ className, title }: LogoMarkProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      className={cn("size-6 shrink-0 text-brand", className)}
    >
      <path d={MARK_BODY_PATH} />
      <path
        d={MARK_TRAIL_PATH}
        className="[clip-path:inset(0_0_0_0)] motion-safe:group-hover/logo:animate-[trail-redraw_900ms_var(--ease-out-expo)]"
      />
    </svg>
  );
}
