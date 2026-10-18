import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { AgentCustomer } from "@/components/agent/agent-customer";

export const metadata: Metadata = { title: "Customer" };

export default function Page({ params }: PageProps<"/app/agent/customers/[id]">) {
  return <WithId params={params}>{(id) => <AgentCustomer id={id} />}</WithId>;
}
