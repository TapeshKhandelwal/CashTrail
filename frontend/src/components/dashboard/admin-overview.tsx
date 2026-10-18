"use client";

import { DashboardView } from "./dashboard-view";

export function AdminOverview() {
  return (
    <DashboardView
      eyebrow="Admin · All branches"
      title="Overview"
      description="Every branch, every hand-off, in one ledger."
      desk="admin"
      team="branches"
      links={{
        discrepancies: "/app/finance/discrepancies",
        deposits: "/app/finance/settlements",
        deposit: (id) => `/app/finance/settlements/${id}`,
        submissions: "/app/branch/submissions",
      }}
    />
  );
}
