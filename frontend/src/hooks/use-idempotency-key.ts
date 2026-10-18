"use client";

import { useCallback, useState } from "react";

import { uuid } from "@/lib/uuid";

/**
 * One UUID per form instance. Retries of the same submission reuse it, so the server returns
 * the original result instead of recording twice; call `rotate()` once a submission succeeds.
 */
export function useIdempotencyKey(): { key: string; rotate: () => void } {
  const [key, setKey] = useState(uuid);
  const rotate = useCallback(() => setKey(uuid()), []);
  return { key, rotate };
}
