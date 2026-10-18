import type { Metadata } from "next";

import { AgentSubmissions } from "@/components/agent/agent-submissions";

export const metadata: Metadata = { title: "Hand-overs" };

export default function Page() {
  return <AgentSubmissions />;
}
