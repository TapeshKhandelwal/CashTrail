import type { Metadata } from "next";

import { BranchDeposits } from "@/components/branch/branch-deposits";

export const metadata: Metadata = { title: "Deposits" };

export default function Page() {
  return <BranchDeposits />;
}
