import type { Metadata } from "next";

import { FinanceDashboard } from "@/components/dashboard/finance-dashboard";

export const metadata: Metadata = { title: "Finance dashboard" };

export default function Page() {
  return <FinanceDashboard />;
}
