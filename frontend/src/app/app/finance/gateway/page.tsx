import type { Metadata } from "next";

import { GatewaySettlements } from "@/components/finance/gateway-settlements";

export const metadata: Metadata = { title: "Gateway settlements" };

export default function Page() {
  return <GatewaySettlements />;
}
