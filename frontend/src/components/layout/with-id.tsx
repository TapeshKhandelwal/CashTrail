import { Suspense, type ReactNode } from "react";

import { DetailSkeleton } from "@/components/feedback/skeletons";

interface WithIdProps {
  params: Promise<{ id: string }>;
  children: (id: number) => ReactNode;
}

/** Detail pages: resolve the `[id]` param inside a Suspense boundary so navigation stays instant. */
export function WithId({ params, children }: WithIdProps) {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <Resolve params={params}>{children}</Resolve>
    </Suspense>
  );
}

async function Resolve({ params, children }: WithIdProps) {
  const { id } = await params;
  return children(Number(id));
}
