import { MapPin, Phone } from "lucide-react";

import { Money } from "@/components/money/money";
import { initials } from "@/lib/format";
import { isZero } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { CustomerDetail } from "@/types/domain";

/** Name, contact and balance strip at the top of a customer page. */
export function CustomerProfile({ customer }: { customer: CustomerDetail }) {
  const overdue = !isZero(customer.overdue_amount);
  return (
    <section className="overflow-hidden rounded-xl border border-rule bg-raised">
      <div className="flex items-start gap-4 px-5 py-5">
        <span aria-hidden className="grid size-12 shrink-0 place-items-center rounded-full border border-rule bg-sunk font-display text-[18px] text-ink">
          {initials(customer.full_name)}
        </span>
        <div className="flex min-w-0 flex-col gap-1.5">
          <p className="font-mono text-[11.5px] text-faint">
            {customer.customer_code} · {customer.branch_code}
            {!customer.is_active && <span className="ml-2 text-st-rejected-fg">Inactive</span>}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-dim">
            {customer.phone && (
              <a href={`tel:${customer.phone}`} className="inline-flex items-center gap-1.5 hover:text-ink">
                <Phone aria-hidden className="size-3.5" />
                <span className="tabular-nums">{customer.phone}</span>
              </a>
            )}
            {customer.address && (
              <span className="inline-flex items-start gap-1.5">
                <MapPin aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {customer.address}
              </span>
            )}
          </div>
          {customer.assigned_agent_name && <p className="text-[12.5px] text-faint">Agent · {customer.assigned_agent_name}</p>}
        </div>
      </div>
      <dl className="grid grid-cols-2 border-t border-rule sm:grid-cols-3">
        {[
          ["Outstanding", <Money key="o" value={customer.outstanding} whole />],
          ["Overdue", <Money key="v" value={customer.overdue_amount} tone={overdue ? "short" : "dim"} />],
          ["Due today", <Money key="d" value={customer.due_today} tone={isZero(customer.due_today) ? "dim" : "none"} />],
        ].map(([label, value], index) => (
          <div
            key={index}
            className={cn(
              "flex min-w-0 flex-col gap-1 border-rule px-5 py-3.5",
              index === 0 && "max-sm:col-span-2",
              index === 1 && "max-sm:border-t sm:border-l",
              index === 2 && "border-l max-sm:border-t",
            )}
          >
            <dt className="eyebrow">{label}</dt>
            <dd className={cn("text-[15px] text-ink tabular-nums", index === 0 && "max-sm:text-[20px] max-sm:font-medium max-sm:tracking-[-0.01em]")}>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
