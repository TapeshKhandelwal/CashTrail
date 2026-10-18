import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { SubmissionVerify } from "@/components/branch/submission-verify";

export const metadata: Metadata = { title: "Count cash" };

export default function Page({ params }: PageProps<"/app/branch/submissions/[id]">) {
  return <WithId params={params}>{(id) => <SubmissionVerify id={id} />}</WithId>;
}
