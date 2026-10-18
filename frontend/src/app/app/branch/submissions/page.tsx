import type { Metadata } from "next";

import { BranchSubmissions } from "@/components/branch/branch-submissions";

export const metadata: Metadata = { title: "Submissions" };

export default function Page() {
  return <BranchSubmissions />;
}
