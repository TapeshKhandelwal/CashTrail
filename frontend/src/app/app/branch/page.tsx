import type { Metadata } from "next";

import { BranchDashboard } from "@/components/dashboard/branch-dashboard";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <BranchDashboard />;
}
