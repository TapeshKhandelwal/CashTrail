import { formatDayMonth, formatTime } from "@/lib/dates";
import type { Collection } from "@/types/domain";

/**
 * Who paid, the receipt number and when, for receipt rows. Phones give the receipt number its
 * own line so it is never cut short; wider screens keep time and number on one line.
 */
export function ReceiptSummary({ receipt }: { receipt: Pick<Collection, "customer_name" | "receipt_number" | "collected_at"> }) {
  const when = `${formatDayMonth(receipt.collected_at)} ${formatTime(receipt.collected_at)}`;
  return (
    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
      <span className="truncate text-[14px] text-ink">{receipt.customer_name}</span>
      <span className="truncate font-mono text-[11.5px] text-faint">
        <span className="max-sm:hidden">{when} · </span>
        {receipt.receipt_number}
      </span>
      <span className="text-[12px] text-faint sm:hidden">{when}</span>
    </span>
  );
}
