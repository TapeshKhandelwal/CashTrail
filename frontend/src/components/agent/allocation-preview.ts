import { fromPaise, toPaise, type MoneyString } from "@/lib/money";
import type { Installment } from "@/types/domain";

export interface PreviewLine {
  installmentNo: number;
  dueDate: string;
  applied: MoneyString;
  clears: boolean;
}

/**
 * Mirrors the server's allocation (oldest unpaid instalment first) so the agent sees what a
 * payment will cover before recording it. The server's allocation is the one that counts.
 */
export function previewAllocation(schedule: Installment[], amount: MoneyString): PreviewLine[] {
  let remaining = toPaise(amount);
  const lines: PreviewLine[] = [];
  for (const row of [...schedule].sort((a, b) => a.installment_no - b.installment_no)) {
    if (remaining <= 0n) break;
    const open = toPaise(row.outstanding);
    if (open <= 0n) continue;
    const applied = remaining < open ? remaining : open;
    remaining -= applied;
    lines.push({ installmentNo: row.installment_no, dueDate: row.due_date, applied: fromPaise(applied), clears: applied === open });
  }
  return lines;
}
