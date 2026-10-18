import type { Metadata } from "next";

import { NewLoan } from "@/components/loans/new-loan";

export const metadata: Metadata = { title: "New loan" };

export default function Page() {
  return <NewLoan basePath="/app/branch" />;
}
