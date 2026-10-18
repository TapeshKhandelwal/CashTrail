import type { Metadata } from "next";

import { BranchesAdmin } from "@/components/admin/branches-admin";

export const metadata: Metadata = { title: "Branches" };

export default function Page() {
  return <BranchesAdmin />;
}
