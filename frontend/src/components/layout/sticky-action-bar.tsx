import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The primary action pinned above the home indicator on phones (it replaces the agent tab bar
 * on form routes); inline at the end of the form from md up. Pair with `<Button size="xl">`.
 */
export function StickyActionBar({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <>
      <div aria-hidden className="h-24 md:hidden" />
      <div
        data-print="hide"
        data-sticky-action
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-paper/92 px-4 pt-3 pb-safe-offset-3 backdrop-blur-md",
          "md:static md:z-auto md:mt-8 md:border-0 md:bg-transparent md:p-0 md:backdrop-blur-none",
          className,
        )}
      >
        <div className="mx-auto flex max-w-[560px] flex-col gap-2 md:max-w-none">{children}</div>
      </div>
    </>
  );
}
