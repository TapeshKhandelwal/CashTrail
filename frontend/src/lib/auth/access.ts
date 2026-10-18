/**
 * Role -> route access. Pure and dependency-free so `proxy.ts`, server helpers and the UI
 * share one definition. Django remains the authority; this only decides where to send people.
 */
import type { Role } from "@/types/domain";

export const ROLE_HOME: Record<Role, string> = {
  AGENT: "/app/agent",
  BRANCH_MANAGER: "/app/branch",
  FINANCE: "/app/finance",
  ADMIN: "/app/admin",
};

export const ROLE_LABEL: Record<Role, string> = {
  AGENT: "Field agent",
  BRANCH_MANAGER: "Branch manager",
  FINANCE: "Finance",
  ADMIN: "Admin",
};

/** Section prefix -> roles allowed in it. Admins operate the branch and finance desks too. */
const SECTION_ROLES: Record<string, readonly Role[]> = {
  "/app/agent": ["AGENT"],
  "/app/branch": ["BRANCH_MANAGER", "ADMIN"],
  "/app/finance": ["FINANCE", "ADMIN"],
  "/app/admin": ["ADMIN"],
};

export function sectionOf(pathname: string): string | null {
  return (
    Object.keys(SECTION_ROLES).find(
      (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
    ) ?? null
  );
}

export function canAccess(role: Role, pathname: string): boolean {
  const section = sectionOf(pathname);
  return section === null || SECTION_ROLES[section].includes(role);
}

export const LOGIN_PATH = "/login";

/** Only same-origin app paths are honoured as post-login destinations. */
export function safeNextPath(next: string | null | undefined, role: Role): string {
  if (next && next.startsWith("/app") && !next.startsWith("//") && canAccess(role, next)) {
    return next;
  }
  return ROLE_HOME[role];
}

export const isRole = (value: unknown): value is Role =>
  value === "AGENT" || value === "BRANCH_MANAGER" || value === "FINANCE" || value === "ADMIN";
