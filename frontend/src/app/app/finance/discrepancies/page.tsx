import type { Metadata } from "next";

import { DiscrepanciesView } from "@/components/discrepancies/discrepancies-view";

export const metadata: Metadata = { title: "Discrepancies" };

export default function Page() {
  return <DiscrepanciesView description="Every gap between what was counted, deposited and credited, and how each was closed." />;
}
