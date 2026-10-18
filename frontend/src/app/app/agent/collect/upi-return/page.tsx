import type { Metadata } from "next";

import { UpiReturn } from "@/components/agent/upi-return";

export const metadata: Metadata = { title: "Confirming payment" };

export default function Page() {
  return <UpiReturn />;
}
