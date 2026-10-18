import { requireRole } from "@/lib/auth/session";

/** Server-side guard for the finance section; proxy.ts redirects optimistically before this. */
export default async function FinanceLayout({ children }: LayoutProps<"/app/finance">) {
  await requireRole("FINANCE", "ADMIN");
  return children;
}
