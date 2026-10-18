import { EmptyState } from "@/components/feedback/empty-state";

import { PageHeader } from "./page-header";

/** Stand-in for a screen that hasn't been built yet; replace the whole page when building it. */
export function ScreenPlaceholder({ eyebrow, title, description }: { eyebrow?: string; title: string; description?: string }) {
  return (
    <>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <EmptyState
        illustration="ledger"
        title="This screen is being built."
        description="Its route, navigation and data layer are ready."
        bordered
      />
    </>
  );
}
