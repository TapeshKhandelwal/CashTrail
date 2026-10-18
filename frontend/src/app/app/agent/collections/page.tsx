import type { Metadata } from "next";

import { AgentHistory } from "@/components/agent/agent-history";

export const metadata: Metadata = { title: "History" };

export default function Page() {
  return <AgentHistory />;
}
