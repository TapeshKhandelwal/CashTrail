import type { Metadata } from "next";

import { AgentToday } from "@/components/agent/agent-today";

export const metadata: Metadata = { title: "Today" };

export default function Page() {
  return <AgentToday />;
}
