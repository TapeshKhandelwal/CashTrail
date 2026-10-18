import {
  ArrowRightLeft,
  Banknote,
  BookUser,
  Building,
  ChartColumn,
  FileDown,
  HandCoins,
  House,
  Inbox,
  Landmark,
  LayoutDashboard,
  NotebookText,
  Plus,
  ReceiptText,
  ScrollText,
  SendHorizontal,
  Smartphone,
  TriangleAlert,
  UserCog,
  Users,
  WalletCards,
  type LucideIcon,
} from "lucide-react";

import type { Role } from "@/types/domain";

/** Live counters shown next to nav items (fed by the reconciliation summary). */
export type NavBadge = "pendingSubmissions" | "openDiscrepancies" | "delayedDeposits";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Match only the exact path (section roots such as dashboards). */
  exact?: boolean;
  badge?: NavBadge;
  /** Extra words the command palette matches on. */
  keywords?: string[];
}

export interface NavGroup {
  /** Rendered as a mono label above the group. */
  label: string;
  items: NavItem[];
}

export interface NavAction {
  title: string;
  href: string;
  icon: LucideIcon;
  shortcut?: string;
}

const AGENT_NAV: NavGroup[] = [
  {
    label: "Today",
    items: [
      { title: "Today", href: "/app/agent", icon: House, exact: true, keywords: ["home", "route", "visits"] },
      { title: "Customers", href: "/app/agent/customers", icon: Users },
      { title: "Collect", href: "/app/agent/collect", icon: Plus, keywords: ["repayment", "receipt", "new collection"] },
    ],
  },
  {
    label: "Cash",
    items: [
      { title: "Hand over", href: "/app/agent/handover", icon: ArrowRightLeft, exact: true, keywords: ["submit cash"] },
      { title: "Hand-overs", href: "/app/agent/handover/submissions", icon: SendHorizontal, keywords: ["submissions"] },
      { title: "History", href: "/app/agent/collections", icon: ReceiptText, keywords: ["collections", "receipts"] },
    ],
  },
];

const BRANCH_RECONCILIATION: NavItem[] = [
  { title: "Submissions", href: "/app/branch/submissions", icon: Inbox, badge: "pendingSubmissions", keywords: ["count cash", "verify"] },
  { title: "Collections", href: "/app/branch/collections", icon: HandCoins, keywords: ["receipts", "repayments"] },
  { title: "Discrepancies", href: "/app/branch/discrepancies", icon: TriangleAlert, badge: "openDiscrepancies" },
];

const BRANCH_MONEY: NavItem[] = [
  { title: "Deposits", href: "/app/branch/deposits", icon: Landmark, keywords: ["bank", "slip"] },
  { title: "Customers", href: "/app/branch/customers", icon: BookUser, keywords: ["borrowers"] },
  { title: "Loans", href: "/app/branch/loans", icon: NotebookText, keywords: ["emi", "schedule", "overdue"] },
];

const FINANCE_MONEY: NavItem[] = [
  { title: "Settlement queue", href: "/app/finance/settlements", icon: WalletCards, badge: "delayedDeposits", keywords: ["deposits", "bank credit"] },
  { title: "Gateway settlements", href: "/app/finance/gateway", icon: Smartphone, keywords: ["upi", "razorpay", "utr"] },
];

const FINANCE_CONTROL: NavItem[] = [
  { title: "Discrepancies", href: "/app/finance/discrepancies", icon: TriangleAlert, badge: "openDiscrepancies" },
  { title: "Reports", href: "/app/finance/reports", icon: FileDown, keywords: ["csv", "export"] },
];

/** Sidebar groups per role; each group renders under a mono label. */
export const NAV: Record<Role, NavGroup[]> = {
  AGENT: AGENT_NAV,
  BRANCH_MANAGER: [
    { label: "Today", items: [{ title: "Dashboard", href: "/app/branch", icon: LayoutDashboard, exact: true }] },
    { label: "Reconciliation", items: BRANCH_RECONCILIATION },
    { label: "Money", items: BRANCH_MONEY },
  ],
  FINANCE: [
    { label: "Today", items: [{ title: "Dashboard", href: "/app/finance", icon: ChartColumn, exact: true }] },
    { label: "Money", items: FINANCE_MONEY },
    { label: "Control", items: FINANCE_CONTROL },
  ],
  ADMIN: [
    { label: "Today", items: [{ title: "Overview", href: "/app/admin", icon: LayoutDashboard, exact: true }] },
    {
      label: "Branch desk",
      items: [
        { title: "Branch dashboard", href: "/app/branch", icon: Building, exact: true },
        ...BRANCH_RECONCILIATION.filter((item) => item.href !== "/app/branch/discrepancies"),
        ...BRANCH_MONEY,
      ],
    },
    {
      label: "Finance desk",
      items: [
        { title: "Finance dashboard", href: "/app/finance", icon: ChartColumn, exact: true },
        ...FINANCE_MONEY,
        ...FINANCE_CONTROL,
      ],
    },
    {
      label: "Admin",
      items: [
        { title: "Branches", href: "/app/admin/branches", icon: Building },
        { title: "Users", href: "/app/admin/users", icon: UserCog, keywords: ["staff", "agents"] },
        { title: "Bank accounts", href: "/app/admin/bank-accounts", icon: Landmark },
        { title: "Audit log", href: "/app/admin/audit", icon: ScrollText, keywords: ["history", "changes"] },
      ],
    },
  ],
};

export interface AgentTab extends NavItem {
  /** The raised ink Collect button. */
  primary?: boolean;
}

/** Agent phones: bottom tabs. "Me" is not a route; the tab bar renders it as a sheet trigger. */
export const AGENT_TABS: AgentTab[] = [
  { title: "Today", href: "/app/agent", icon: House, exact: true },
  { title: "Customers", href: "/app/agent/customers", icon: Users },
  { title: "Collect", href: "/app/agent/collect", icon: Plus, primary: true },
  { title: "Cash", href: "/app/agent/handover", icon: Banknote },
];

/** Routes where the agent tab bar gives way to a sticky action bar. */
export const AGENT_FORM_ROUTES = ["/app/agent/collect", "/app/agent/handover"];

export const NAV_ACTIONS: Record<Role, NavAction[]> = {
  AGENT: [
    { title: "New collection", href: "/app/agent/collect", icon: Plus },
    { title: "Hand over cash", href: "/app/agent/handover", icon: ArrowRightLeft },
  ],
  BRANCH_MANAGER: [
    { title: "Count pending cash", href: "/app/branch/submissions", icon: Inbox },
    { title: "Create deposit", href: "/app/branch/deposits/new", icon: Landmark },
    { title: "New loan", href: "/app/branch/loans/new", icon: Plus },
  ],
  FINANCE: [
    { title: "Record settlement", href: "/app/finance/settlements", icon: WalletCards },
    { title: "Record gateway settlement", href: "/app/finance/gateway", icon: Smartphone },
    { title: "Download reports", href: "/app/finance/reports", icon: FileDown },
  ],
  ADMIN: [
    { title: "Create deposit", href: "/app/branch/deposits/new", icon: Landmark },
    { title: "Record settlement", href: "/app/finance/settlements", icon: WalletCards },
    { title: "Add user", href: "/app/admin/users", icon: UserCog },
  ],
};

export function isActive(item: Pick<NavItem, "href" | "exact">, pathname: string): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

/** Flat list of every nav item a role can reach (command palette, breadcrumbs). */
export function navItems(role: Role): NavItem[] {
  return NAV[role].flatMap((group) => group.items);
}

/** Most specific nav item for a path, used for page titles and breadcrumbs. */
export function activeNavItem(role: Role, pathname: string): NavItem | undefined {
  return navItems(role)
    .filter((item) => pathname === item.href || pathname.startsWith(`${item.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
}
