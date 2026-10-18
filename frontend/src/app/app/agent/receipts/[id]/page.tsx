import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { ReceiptView } from "@/components/agent/receipt-view";

export const metadata: Metadata = { title: "Receipt" };

export default function Page({ params }: PageProps<"/app/agent/receipts/[id]">) {
  return <WithId params={params}>{(id) => <ReceiptView id={id} />}</WithId>;
}
