import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { FinanceDeposit } from "@/components/finance/finance-deposit";

export const metadata: Metadata = { title: "Deposit" };

export default function Page({ params }: PageProps<"/app/finance/settlements/[id]">) {
  return <WithId params={params}>{(id) => <FinanceDeposit id={id} />}</WithId>;
}
