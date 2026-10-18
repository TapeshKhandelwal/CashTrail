"use client";

import { DepositDetailView } from "@/components/deposits/deposit-detail";
import type { ID } from "@/types/domain";

export function BranchDeposit({ id }: { id: ID }) {
  return <DepositDetailView id={id} submissionHref={(submission) => `/app/branch/submissions/${submission}`} />;
}
