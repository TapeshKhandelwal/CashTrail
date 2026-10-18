import type { Metadata } from "next";

import { WithId } from "@/components/layout/with-id";
import { CustomerDetail } from "@/components/customers/customer-detail";

export const metadata: Metadata = { title: "Customer" };

export default function Page({ params }: PageProps<"/app/branch/customers/[id]">) {
  return <WithId params={params}>{(id) => <CustomerDetail id={id} basePath="/app/branch" />}</WithId>;
}
