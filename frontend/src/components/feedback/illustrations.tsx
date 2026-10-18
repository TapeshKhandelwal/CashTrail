import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type IllustrationName = "ledger" | "receipt" | "cash" | "inbox" | "search" | "settled" | "bank";

/* Line drawings on a 96×64 grid, 1.25px strokes, drawn in ink at low opacity. */
const DRAWINGS: Record<IllustrationName, ReactNode> = {
  ledger: (
    <>
      <rect x="22" y="6" width="52" height="52" rx="4" />
      <path d="M32 6v52" className="opacity-60" />
      <path d="M38 18h28M38 26h28M38 34h20M38 42h24" />
      <path d="M61 34h5" className="opacity-60" />
    </>
  ),
  receipt: (
    <>
      <path d="M30 6h36v50l-4.5-3-4.5 3-4.5-3-4.5 3-4.5-3-4.5 3-4.5-3-4.5 3z" />
      <path d="M37 17h22M37 24h14M37 33h22" />
      <path d="M50 42h9" strokeWidth="2" />
    </>
  ),
  cash: (
    <>
      <rect x="16" y="16" width="64" height="34" rx="3" />
      <rect x="22" y="10" width="64" height="34" rx="3" className="opacity-50" />
      <circle cx="48" cy="33" r="7" />
      <path d="M24 24v18M72 24v18" className="opacity-60" />
    </>
  ),
  inbox: (
    <>
      <path d="M18 34l8-22h44l8 22v18a3 3 0 0 1-3 3H21a3 3 0 0 1-3-3z" />
      <path d="M18 34h18l3 7h18l3-7h18" />
      <path d="M36 21h24M38 27h20" className="opacity-60" />
    </>
  ),
  search: (
    <>
      <path d="M16 14h40M16 22h30M16 30h24" className="opacity-60" />
      <circle cx="58" cy="36" r="13" />
      <path d="M67.5 45.5l11 11" strokeWidth="2" />
    </>
  ),
  settled: (
    <>
      <circle cx="48" cy="32" r="22" />
      <path d="M38 32.5l7 7 13-14" strokeWidth="1.75" />
      <path d="M12 32h8M76 32h8" className="opacity-60" />
    </>
  ),
  bank: (
    <>
      <path d="M18 24L48 9l30 15z" />
      <path d="M24 28v20M36 28v20M60 28v20M72 28v20" />
      <path d="M16 54h64M20 50h56" />
    </>
  ),
};

/** Small line illustration for empty and error states; never cartoons. */
export function Illustration({ name, className }: { name: IllustrationName; className?: string }) {
  return (
    <svg
      viewBox="0 0 96 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={cn("h-16 w-24 text-ink/25", className)}
    >
      {DRAWINGS[name]}
    </svg>
  );
}
