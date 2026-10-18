import { requireRole } from "@/lib/auth/session";

/** Server-side guard for the agent section; proxy.ts redirects optimistically before this. */
export default async function AgentLayout({ children }: LayoutProps<"/app/agent">) {
  await requireRole("AGENT");
  return children;
}
