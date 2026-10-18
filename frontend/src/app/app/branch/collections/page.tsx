import type { Metadata } from "next";

import { BranchCollections } from "@/components/branch/branch-collections";

export const metadata: Metadata = { title: "Collections" };

export default function Page() {
  return <BranchCollections />;
}
