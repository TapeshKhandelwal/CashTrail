"use client";

import { DepositDetailView } from "@/components/deposits/deposit-detail";
import type { ID } from "@/types/domain";

export function FinanceDeposit({ id }: { id: ID }) {
  return <DepositDetailView id={id} />;
}
