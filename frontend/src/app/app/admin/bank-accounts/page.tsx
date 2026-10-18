import type { Metadata } from "next";

import { BankAccountsAdmin } from "@/components/admin/bank-accounts-admin";

export const metadata: Metadata = { title: "Bank accounts" };

export default function Page() {
  return <BankAccountsAdmin />;
}
