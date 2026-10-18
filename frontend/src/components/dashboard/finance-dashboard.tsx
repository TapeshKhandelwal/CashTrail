"use client";

import { DashboardView } from "./dashboard-view";

export function FinanceDashboard() {
  return (
    <DashboardView
      eyebrow="Finance · All branches"
      title="Dashboard"
      description="Branch cash and UPI, from collection to the company account."
      desk="finance"
      team="branches"
      links={{
        discrepancies: "/app/finance/discrepancies",
        deposits: "/app/finance/settlements",
        deposit: (id) => `/app/finance/settlements/${id}`,
      }}
    />
  );
}
