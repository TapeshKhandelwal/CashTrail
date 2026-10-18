import type { Metadata } from "next";

import { CollectFlow } from "@/components/agent/collect-flow";

export const metadata: Metadata = { title: "Collect" };

export default function Page() {
  return <CollectFlow />;
}
