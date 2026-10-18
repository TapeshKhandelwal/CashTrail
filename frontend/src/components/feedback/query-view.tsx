"use client";

import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import type { ApiError } from "@/lib/api/errors";

import { ErrorState } from "./error-state";
import { StillLoading } from "./skeletons";

interface QueryViewProps<T> {
  query: UseQueryResult<T, ApiError>;
  /** Layout-matched skeleton. */
  loading: ReactNode;
  /** Rendered when `isEmpty(data)` is true. */
  empty?: ReactNode;
  isEmpty?: (data: T) => boolean;
  errorTitle?: string;
  children: (data: T) => ReactNode;
}

/**
 * The loading / error / empty / data switch every data view needs.
 *
 *   <QueryView query={useQuery(customerQueries.detail(id))} loading={<DetailSkeleton />}>
 *     {(customer) => <CustomerCard customer={customer} />}
 *   </QueryView>
 */
export function QueryView<T>({ query, loading, empty, isEmpty, errorTitle, children }: QueryViewProps<T>) {
  if (query.isPending) {
    return (
      <>
        {loading}
        <StillLoading onRetry={() => void query.refetch()} />
      </>
    );
  }
  if (query.isError) {
    return <ErrorState error={query.error} title={errorTitle} onRetry={() => void query.refetch()} />;
  }
  if (empty && isEmpty?.(query.data)) return <>{empty}</>;
  return <>{children(query.data)}</>;
}
