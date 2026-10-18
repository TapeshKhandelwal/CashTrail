import { ChevronRight } from "lucide-react";
import Link from "next/link";

import { Money } from "@/components/money/money";
import { formatDayMonth, todayIST } from "@/lib/dates";
import { initials } from "@/lib/format";
import { isZero } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Customer } from "@/types/domain";

/** One stop on the agent's route: who, what is due, and how urgent it is. */
export function CustomerRow({ customer }: { customer: Customer }) {
  const overdue = !isZero(customer.overdue_amount);
  const dueToday = !isZero(customer.due_today);
  const today = todayIST();

  return (
    <Link
      href={`/app/agent/customers/${customer.id}`}
      className="group flex items-center gap-3.5 px-4 py-3.5 transition-colors outline-none hover:bg-sunk/60 focus-visible:bg-sunk sm:px-5"
    >
      <span
        aria-hidden
        className={cn(
          "grid size-10 shrink-0 place-items-center rounded-full border text-[12.5px] font-medium",
          overdue ? "border-st-short/30 bg-st-short/6 text-st-short-fg" : "border-rule bg-sunk text-dim",
        )}
      >
        {initials(customer.full_name)}
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="truncate text-[14.5px] text-ink">{customer.full_name}</span>
        <span className="text-[12.5px] text-faint">
          <span className="font-mono">{customer.customer_code}</span>
          {customer.next_due_date && (
            <>
              <span className="max-sm:hidden"> · </span>
              <span className="whitespace-nowrap max-sm:block">
                {customer.next_due_date === today
                  ? "due today"
                  : `${customer.next_due_date < today ? "due" : "next"} ${formatDayMonth(customer.next_due_date)}`}
              </span>
            </>
          )}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-0.5">
        {overdue ? (
          <>
            <Money value={customer.overdue_amount} className="text-[14px] text-st-short-fg" />
            <span className="text-[11.5px] text-st-short-fg">overdue</span>
          </>
        ) : dueToday ? (
          <>
            <Money value={customer.due_today} className="text-[14px] text-ink" />
            <span className="text-[11.5px] text-st-collected-fg">due today</span>
          </>
        ) : (
          <>
            <Money value={customer.outstanding} whole className="text-[14px] text-dim" />
            <span className="text-[11.5px] text-faint">outstanding</span>
          </>
        )}
      </span>
      <ChevronRight aria-hidden className="size-4 shrink-0 text-faint transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}
