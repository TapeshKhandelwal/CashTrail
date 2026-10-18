import { Money } from "@/components/money/money";
import { StatusChip } from "@/components/status/status-chip";
import { formatDate } from "@/lib/dates";
import type { Deposit } from "@/types/domain";

/**
 * A deposit as one phone card: reference and amount, status and branch, the bank line, and
 * what was credited against it.
 */
export function DepositCard({ deposit }: { deposit: Deposit }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span className="min-w-0 truncate font-mono text-[13px] text-ink">{deposit.deposit_number}</span>
        <Money value={deposit.deposited_amount} className="shrink-0 text-[15px] font-medium text-ink" />
      </div>
      <div className="flex items-center justify-between gap-3">
        <StatusChip
          kind="deposit"
          status={deposit.status}
          isDelayed={deposit.is_delayed}
          daysPending={deposit.days_pending}
          withIcon={deposit.is_delayed}
        />
        {deposit.settled_amount && (
          <span className="shrink-0 text-[12.5px] text-faint">
            Credited <Money value={deposit.settled_amount} tone="settled" />
          </span>
        )}
      </div>
      <p className="mt-1 truncate text-[12.5px] text-dim">
        {deposit.bank_account.bank_name} {deposit.bank_account.masked_account_number} · {formatDate(deposit.deposit_date)}
      </p>
      <p className="truncate font-mono text-[11.5px] text-faint">
        {deposit.branch_code && `${deposit.branch_code} · `}
        {deposit.reference_number}
      </p>
    </div>
  );
}
