import { requireRole } from "@/lib/auth/session";

/** Server-side guard for the admin section; proxy.ts redirects optimistically before this. */
export default async function AdminLayout({ children }: LayoutProps<"/app/admin">) {
  await requireRole("ADMIN");
  return children;
}
