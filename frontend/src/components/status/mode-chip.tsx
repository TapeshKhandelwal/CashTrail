import { PAYMENT_MODE } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { PaymentMode } from "@/types/domain";

/** Payment mode is a neutral marker, not a status: Cash in ink, UPI in the UPI colour. */
export function ModeChip({ mode, className }: { mode: PaymentMode; className?: string }) {
  const { label, icon: Icon, className: tone } = PAYMENT_MODE[mode];
  return (
    <span className={cn("inline-flex w-fit shrink-0 items-center gap-1 font-mono text-[11px] tracking-[0.08em] uppercase", tone, className)}>
      <Icon aria-hidden className="size-3.5" strokeWidth={1.6} />
      {label}
    </span>
  );
}
