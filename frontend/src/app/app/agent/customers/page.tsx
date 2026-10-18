import type { Metadata } from "next";

import { AgentCustomers } from "@/components/agent/agent-customers";

export const metadata: Metadata = { title: "Customers" };

export default function Page() {
  return <AgentCustomers />;
}
