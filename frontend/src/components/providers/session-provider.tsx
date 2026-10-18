"use client";

import { createContext, use, type ReactNode } from "react";

import type { SessionUser } from "@/lib/auth/tokens";

const SessionContext = createContext<SessionUser | null>(null);

/** Hands the server-read session to client components inside the app shell. */
export function SessionProvider({ user, children }: { user: SessionUser; children: ReactNode }) {
  return <SessionContext value={user}>{children}</SessionContext>;
}

/** The signed-in user (role, branch, names). Only valid inside `/app`. */
export function useSession(): SessionUser {
  const user = use(SessionContext);
  if (!user) throw new Error("useSession must be used inside the app shell");
  return user;
}
