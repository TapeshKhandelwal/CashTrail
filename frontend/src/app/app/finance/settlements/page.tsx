import type { Metadata } from "next";

import { SettlementQueue } from "@/components/finance/settlement-queue";

export const metadata: Metadata = { title: "Settlement queue" };

export default function Page() {
  return <SettlementQueue />;
}
