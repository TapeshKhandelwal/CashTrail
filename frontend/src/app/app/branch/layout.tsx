import { requireRole } from "@/lib/auth/session";

/** Server-side guard for the branch section; proxy.ts redirects optimistically before this. */
export default async function BranchLayout({ children }: LayoutProps<"/app/branch">) {
  await requireRole("BRANCH_MANAGER", "ADMIN");
  return children;
}
