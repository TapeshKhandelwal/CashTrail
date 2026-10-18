import type { Metadata } from "next";

import { LoansView } from "@/components/loans/loans-view";

export const metadata: Metadata = { title: "Loans" };

export default function Page() {
  return <LoansView basePath="/app/branch" />;
}
