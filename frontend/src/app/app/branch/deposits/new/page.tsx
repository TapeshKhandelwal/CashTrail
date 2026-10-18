import type { Metadata } from "next";

import { NewDeposit } from "@/components/branch/new-deposit";

export const metadata: Metadata = { title: "New deposit" };

export default function Page() {
  return <NewDeposit />;
}
