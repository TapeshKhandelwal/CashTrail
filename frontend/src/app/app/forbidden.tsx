import Link from "next/link";

import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";

export default function AppForbidden() {
  return (
    <EmptyState
      illustration="ledger"
      title="You don't have access to this page."
      description="Your role or branch doesn't cover it. Ask an admin if you think it should."
      bordered
      action={
        <Button asChild>
          <Link href="/app">Go to my home</Link>
        </Button>
      }
    />
  );
}
