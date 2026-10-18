import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { BranchDeposit } from "@/components/branch/branch-deposit";

export const metadata: Metadata = { title: "Deposit" };

export default function Page({ params }: PageProps<"/app/branch/deposits/[id]">) {
  return <WithId params={params}>{(id) => <BranchDeposit id={id} />}</WithId>;
}
