"use client";

import type { ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

export type ConfirmTone = "default" | "destructive";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  /** Restate what is about to happen, amounts first (static <Money>, never rolling). */
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** `destructive` is the one place solid rose is used. */
  tone?: ConfirmTone;
  onConfirm: () => void;
  /** Mutation in flight: confirm shows a spinner and the dialog can't be dismissed. */
  loading?: boolean;
  confirmDisabled?: boolean;
}

/**
 * Confirmation for irreversible actions (approve, reject, settle, mark failed, void). Keep it
 * open while the mutation runs and close it from the mutation's onSuccess.
 *
 *   <ConfirmDialog open={open} onOpenChange={setOpen} title="Approve this count?" confirmLabel="Approve ₹48,500"
 *     loading={approve.isPending} onConfirm={() => approve.mutate(...)}>
 *     <ConfirmFacts rows={[["Expected", <Money value={…} />], ["Counted", <Money value={…} />]]} />
 *   </ConfirmDialog>
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  loading = false,
  confirmDisabled = false,
}: ConfirmDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={(next) => !loading && onOpenChange(next)}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>{cancelLabel}</AlertDialogCancel>
          <Button
            variant={tone === "destructive" ? "destructive-solid" : "default"}
            loading={loading}
            disabled={confirmDisabled}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** The amounts and references a confirmation restates, as a ruled two-column list. */
export function ConfirmFacts({ rows }: { rows: [label: ReactNode, value: ReactNode][] }) {
  return (
    <dl className="divide-y divide-rule overflow-hidden rounded-lg border border-rule bg-sunk/50 text-[13.5px]">
      {rows.map(([label, value], index) => (
        <div key={index} className="flex items-baseline justify-between gap-4 px-3.5 py-2.5">
          <dt className="text-dim">{label}</dt>
          <dd className="text-right font-medium text-ink tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
