import { redirect } from "next/navigation";

import { ROLE_HOME } from "@/lib/auth/access";
import { requireSession } from "@/lib/auth/session";

/** PWA start URL: send each role to its home (proxy.ts usually does this first). */
export default async function AppHome() {
  const { user } = await requireSession();
  redirect(ROLE_HOME[user.role]);
}
