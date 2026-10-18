import { RecordCard } from "@/components/branch/record-card";
import { createColumns } from "@/components/data-table/data-table-features";
import { Money } from "@/components/money/money";
import { StatusChip } from "@/components/status/status-chip";
import { formatDate } from "@/lib/dates";
import type { FilterDef } from "@/hooks/use-data-table-state";
import type { Deposit } from "@/types/domain";

const col = createColumns<Deposit>();

export const DEPOSIT_COLUMNS = col.columns([
  col.accessor("deposit_number", { header: "Deposit", meta: { mono: true, card: "title" } }),
  col.display({
    id: "bank",
    header: "Bank",
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span>{row.original.bank_account.bank_name}</span>
        <span className="font-mono text-[11.5px] text-faint">
          {row.original.bank_account.masked_account_number} · {row.original.reference_number}
        </span>
      </span>
    ),
  }),
  col.accessor("branch_code", {
    header: "Branch",
    cell: ({ getValue }) => <span className="font-mono text-[12px] text-dim">{getValue() ?? "UPI"}</span>,
  }),
  col.accessor("deposit_date", {
    header: "Deposited",
    enableSorting: true,
    cell: ({ getValue }) => <span className="text-dim">{formatDate(getValue())}</span>,
  }),
  col.accessor("deposited_amount", {
    header: "Amount",
    enableSorting: true,
    meta: { align: "end", card: "amount" },
    cell: ({ getValue }) => <Money value={getValue()} />,
  }),
  col.accessor("settled_amount", {
    header: "Settled",
    meta: { align: "end" },
    cell: ({ getValue }) => {
      const value = getValue();
      return value ? <Money value={value} tone="settled" /> : <span className="text-faint">—</span>;
    },
  }),
  col.accessor("status", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ row }) => (
      <StatusChip kind="deposit" status={row.original.status} isDelayed={row.original.is_delayed} daysPending={row.original.days_pending} withIcon={row.original.is_delayed} />
    ),
  }),
]);

/** Phone card for a deposit row: `renderCard={(row) => <DepositCard deposit={row} />}`. */
export function DepositCard({ deposit }: { deposit: Deposit }) {
  return (
    <RecordCard
      mono
      title={deposit.deposit_number}
      subtitle={`${deposit.bank_account.bank_name} ${deposit.bank_account.masked_account_number}`}
      amount={<Money value={deposit.deposited_amount} />}
      badge={
        <StatusChip kind="deposit" status={deposit.status} isDelayed={deposit.is_delayed} daysPending={deposit.days_pending} withIcon={deposit.is_delayed} size="sm" />
      }
      meta={[
        formatDate(deposit.deposit_date),
        <span key="ref" className="font-mono text-[11.5px]">
          {deposit.reference_number}
        </span>,
        deposit.settled_amount && (
          <span key="settled">
            Settled <Money value={deposit.settled_amount} tone="settled" />
          </span>
        ),
      ]}
    />
  );
}

export const DEPOSIT_FILTERS: FilterDef[] = [
  {
    type: "multi",
    key: "status",
    label: "Status",
    options: [
      { value: "PENDING", label: "Awaiting settlement" },
      { value: "SETTLED", label: "Settled" },
      { value: "SETTLED_WITH_MISMATCH", label: "Settled with mismatch" },
      { value: "FAILED", label: "Failed" },
    ],
  },
  { type: "boolean", key: "delayed", label: "Past SLA" },
  { type: "dateRange", label: "Deposited", from: "date_from", to: "date_to" },
];
