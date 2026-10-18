import {
  collectionStatus,
  depositStatus,
  discrepancyStatus,
  gatewayOrderStatus,
  installmentStatus,
  loanStatus,
  submissionStatus,
  TONE_CLASSES,
  type StatusMeta,
} from "@/lib/status";
import { cn } from "@/lib/utils";
import type {
  CollectionStatus,
  DepositStatus,
  DiscrepancyDirection,
  DiscrepancyStatus,
  GatewayOrderStatus,
  InstallmentStatus,
  ISODate,
  LoanStatus,
  Money,
  SubmissionStatus,
} from "@/types/domain";

export type StatusInput =
  | { kind: "collection"; status: CollectionStatus }
  | { kind: "submission"; status: SubmissionStatus; difference?: Money | null }
  | { kind: "deposit"; status: DepositStatus; isDelayed?: boolean; daysPending?: number | null }
  | { kind: "discrepancy"; status: DiscrepancyStatus; direction?: DiscrepancyDirection }
  | { kind: "installment"; status: InstallmentStatus; isOverdue: boolean; dueDate: ISODate }
  | { kind: "gatewayOrder"; status: GatewayOrderStatus }
  | { kind: "loan"; status: LoanStatus }
  | { kind: "custom"; meta: StatusMeta };

export function resolveStatus(input: StatusInput): StatusMeta {
  switch (input.kind) {
    case "collection":
      return collectionStatus(input.status);
    case "submission":
      return submissionStatus(input.status, input.difference);
    case "deposit":
      return depositStatus(input.status, { isDelayed: input.isDelayed ?? false, daysPending: input.daysPending ?? null });
    case "discrepancy":
      return discrepancyStatus(input.status, input.direction);
    case "installment":
      return installmentStatus({ status: input.status, is_overdue: input.isOverdue, due_date: input.dueDate });
    case "gatewayOrder":
      return gatewayOrderStatus(input.status);
    case "loan":
      return loanStatus(input.status);
    case "custom":
      return input.meta;
  }
}

type StatusChipProps = StatusInput & {
  /** A ~7% wash of the status colour behind the label (dense tables usually go without). */
  wash?: boolean;
  /** Adds the status icon after the dot (delayed, overdue). */
  withIcon?: boolean;
  size?: "sm" | "md";
  className?: string;
};

/**
 * Status is always a 6px dot plus a label in the darkened status colour, never colour alone.
 *
 *   <StatusChip kind="collection" status={row.status} />
 *   <StatusChip kind="deposit" status={d.status} isDelayed={d.is_delayed} daysPending={d.days_pending} withIcon />
 */
export function StatusChip({ wash = false, withIcon = false, size = "md", className, ...input }: StatusChipProps) {
  const meta = resolveStatus(input as StatusInput);
  const tone = TONE_CLASSES[meta.tone];
  const Icon = meta.icon;
  return (
    <span
      data-tone={meta.tone}
      className={cn(
        "inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full font-medium whitespace-nowrap",
        size === "sm" ? "text-[11.5px]" : "text-[12.5px]",
        wash ? cn("px-2 py-0.5", tone.wash) : "",
        tone.text,
        className,
      )}
    >
      <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full transition-colors duration-200", tone.dot)} />
      {withIcon && <Icon aria-hidden className="size-3.5" strokeWidth={1.75} />}
      <span className={cn(meta.strike && "line-through decoration-1")}>{meta.label}</span>
    </span>
  );
}
