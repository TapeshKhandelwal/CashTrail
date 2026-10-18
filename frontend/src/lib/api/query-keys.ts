/**
 * Every TanStack Query key in the app. Keys are hierarchical so a mutation can invalidate a
 * whole domain (`qk.collections.all`) or a single record (`qk.collections.detail(id)`).
 */
import type { ID } from "@/types/domain";

const domain = <const T extends string>(name: T) => ({
  all: [name] as const,
  lists: () => [name, "list"] as const,
  list: (params: object = {}) => [name, "list", params] as const,
  detail: (id: ID | string) => [name, "detail", id] as const,
});

export const qk = {
  me: ["me"] as const,
  branches: domain("branches"),
  users: domain("users"),
  bankAccounts: domain("bank-accounts"),
  customers: {
    ...domain("customers"),
    loans: (id: ID) => ["customers", "detail", id, "loans"] as const,
    agentRoute: (params: object = {}) => ["customers", "agent-route", params] as const,
  },
  loans: {
    ...domain("loans"),
    schedule: (id: ID) => ["loans", "detail", id, "schedule"] as const,
    repayments: (id: ID, params: object = {}) => ["loans", "detail", id, "repayments", params] as const,
    schedulePreview: (params: object) => ["loans", "schedule-preview", params] as const,
  },
  collections: {
    ...domain("collections"),
    dailySummary: (params: object = {}) => ["collections", "daily-summary", params] as const,
  },
  submissions: domain("submissions"),
  discrepancies: domain("discrepancies"),
  reconciliation: {
    all: ["reconciliation"] as const,
    branchSummary: (params: object = {}) => ["reconciliation", "branch-summary", params] as const,
    agentsSummary: (params: object = {}) => ["reconciliation", "agents-summary", params] as const,
  },
  deposits: {
    ...domain("deposits"),
    pendingCash: (params: object = {}) => ["deposits", "pending-cash", params] as const,
  },
  gatewaySettlements: {
    ...domain("gateway-settlements"),
    pending: (params: object = {}) => ["gateway-settlements", "pending", params] as const,
  },
  payments: {
    ...domain("payments"),
    config: ["payments", "config"] as const,
    confirmation: (id: ID) => ["payments", "detail", id, "confirmation"] as const,
  },
  dashboard: {
    all: ["dashboard"] as const,
    summary: (params: object = {}) => ["dashboard", "summary", params] as const,
    trend: (params: object = {}) => ["dashboard", "trend", params] as const,
    lifecycle: (params: object = {}) => ["dashboard", "lifecycle", params] as const,
    branches: (params: object = {}) => ["dashboard", "branches", params] as const,
    agents: (params: object = {}) => ["dashboard", "agents", params] as const,
  },
  reports: {
    preview: (name: string, params: object = {}) => ["reports", name, params] as const,
  },
  audit: domain("audit-logs"),
} as const;

/** Everything a money movement can change: refresh these after any lifecycle mutation. */
export const MONEY_KEYS = [
  qk.collections.all,
  qk.submissions.all,
  qk.deposits.all,
  qk.gatewaySettlements.all,
  qk.discrepancies.all,
  qk.reconciliation.all,
  qk.dashboard.all,
  qk.customers.all,
  qk.loans.all,
] as const;
