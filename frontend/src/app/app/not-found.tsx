import Link from "next/link";

import { EmptyState } from "@/components/feedback/empty-state";
import { Button } from "@/components/ui/button";

export default function AppNotFound() {
  return (
    <EmptyState
      illustration="search"
      title="This page doesn't exist."
      description="The record may have moved, or it's outside your branch or role."
      bordered
      action={
        <Button asChild>
          <Link href="/app">Go to my home</Link>
        </Button>
      }
    />
  );
}
