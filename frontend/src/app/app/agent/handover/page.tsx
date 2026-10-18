import type { Metadata } from "next";

import { HandoverFlow } from "@/components/agent/handover-flow";

export const metadata: Metadata = { title: "Hand over cash" };

export default function Page() {
  return <HandoverFlow />;
}
