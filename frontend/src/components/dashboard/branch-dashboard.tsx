"use client";

import { useSession } from "@/components/providers/session-provider";

import { DashboardView } from "./dashboard-view";

export function BranchDashboard() {
  const user = useSession();
  return (
    <DashboardView
      eyebrow={user.branch_code ? `${user.branch_code} · ${user.branch_name}` : "Branch desk"}
      title="Dashboard"
      description="What was due, what came in, and where every rupee is now."
      desk="branch"
      team="agents"
      links={{
        discrepancies: "/app/branch/discrepancies",
        deposits: "/app/branch/deposits",
        deposit: (id) => `/app/branch/deposits/${id}`,
        submissions: "/app/branch/submissions",
        atBranch: "/app/branch/deposits/new",
      }}
    />
  );
}
