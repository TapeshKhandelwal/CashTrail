import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { AgentSubmission } from "@/components/agent/agent-submissions";

export const metadata: Metadata = { title: "Hand-over" };

export default function Page({ params }: PageProps<"/app/agent/handover/submissions/[id]">) {
  return <WithId params={params}>{(id) => <AgentSubmission id={id} />}</WithId>;
}
