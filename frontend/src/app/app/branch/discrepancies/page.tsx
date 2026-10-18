import type { Metadata } from "next";

import { DiscrepanciesView } from "@/components/discrepancies/discrepancies-view";

export const metadata: Metadata = { title: "Discrepancies" };

export default function Page() {
  return <DiscrepanciesView description="Shortages and excess found when counting agents' cash, and how each was settled." />;
}
