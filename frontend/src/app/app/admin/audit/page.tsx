import type { Metadata } from "next";

import { AuditLogView } from "@/components/admin/audit-log";

export const metadata: Metadata = { title: "Audit log" };

export default function Page() {
  return <AuditLogView />;
}
