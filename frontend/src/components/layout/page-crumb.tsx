"use client";

import { useEffect, useSyncExternalStore } from "react";

let current: string | null = null;
const listeners = new Set<() => void>();

function setCrumb(label: string | null) {
  current = label;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The detail page's own breadcrumb label, read by the top bar. */
export const usePageCrumb = () => useSyncExternalStore(subscribe, () => current, () => null);

/**
 * Names the last breadcrumb on a detail page (otherwise it reads "Details").
 *
 *   <PageCrumb label={submission.submission_number} />
 */
export function PageCrumb({ label }: { label: string | null | undefined }) {
  useEffect(() => {
    setCrumb(label ?? null);
    return () => setCrumb(null);
  }, [label]);
  return null;
}
