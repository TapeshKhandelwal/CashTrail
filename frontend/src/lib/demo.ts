import type { Role } from "@/types/domain";

/** Demo-role quick sign-in on the login page; matches the backend `seed_demo` staff. */
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const DEMO_PASSWORD = "Demo@12345";

export interface DemoAccount {
  role: Role;
  label: string;
  /** What this role does, in a few words. */
  duty: string;
  username: string;
  password: string;
}

export const DEMO_ACCOUNTS: readonly DemoAccount[] = [
  { role: "AGENT", label: "Agent", duty: "Collects at the doorstep", username: "agent.blr1", password: DEMO_PASSWORD },
  { role: "BRANCH_MANAGER", label: "Branch manager", duty: "Counts and deposits", username: "manager.blr", password: DEMO_PASSWORD },
  { role: "FINANCE", label: "Finance", duty: "Matches the bank", username: "finance", password: DEMO_PASSWORD },
  { role: "ADMIN", label: "Admin", duty: "Sees every branch", username: "admin", password: DEMO_PASSWORD },
];
