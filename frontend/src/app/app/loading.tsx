import { PageHeaderSkeleton, TableSkeleton } from "@/components/feedback/skeletons";

export default function Loading() {
  return (
    <div aria-busy="true">
      <span className="sr-only" role="status">
        Loading…
      </span>
      <PageHeaderSkeleton />
      <TableSkeleton rows={6} />
    </div>
  );
}
