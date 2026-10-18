"use client";

import { UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { AGENT_FORM_ROUTES, AGENT_TABS, isActive } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { MeSheet } from "./me-sheet";

const TAB =
  "relative flex min-h-12 w-full touch-manipulation flex-col items-center justify-center gap-1 text-[10.5px] font-medium tracking-[0.01em] transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset";

/**
 * Agent phones: Today · Customers · Collect · Cash · Me. Collect is the raised ink key; Me opens
 * a sheet rather than a page. Gives way to a sticky action bar on form routes.
 */
export function BottomTabBar() {
  const pathname = usePathname();
  const [meOpen, setMeOpen] = useState(false);
  if (AGENT_FORM_ROUTES.includes(pathname)) return null;

  return (
    <>
      <nav
        aria-label="Main"
        data-print="hide"
        data-bottom-bar
        className="fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-paper/90 pb-safe backdrop-blur-md md:hidden"
      >
        <ul className="mx-auto grid h-16 max-w-[560px] grid-cols-5 items-center px-1">
          {AGENT_TABS.map((tab) => {
            const active = isActive(tab, pathname);
            if (tab.primary) {
              return (
                <li key={tab.href} className="flex justify-center">
                  <Link
                    href={tab.href}
                    aria-current={active ? "page" : undefined}
                    className="flex h-12 w-14 touch-manipulation flex-col items-center justify-center gap-0.5 rounded-xl bg-ink text-paper shadow-lift transition-transform outline-none active:scale-[0.97] focus-visible:ring-3 focus-visible:ring-focus"
                  >
                    <tab.icon className="size-5" strokeWidth={1.8} aria-hidden />
                    <span className="text-[10px] font-medium">{tab.title}</span>
                  </Link>
                </li>
              );
            }
            return (
              <li key={tab.href}>
                <Link
                  href={tab.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(TAB, active ? "text-ink" : "text-faint")}
                >
                  {active && <span aria-hidden className="absolute top-0 h-0.5 w-6 rounded-full bg-brand" />}
                  <tab.icon className="size-5" strokeWidth={active ? 1.8 : 1.5} aria-hidden />
                  {tab.title}
                </Link>
              </li>
            );
          })}
          <li>
            <button
              type="button"
              onClick={() => setMeOpen(true)}
              aria-haspopup="dialog"
              className={cn(TAB, meOpen ? "text-ink" : "text-faint")}
            >
              <UserRound className="size-5" strokeWidth={1.5} aria-hidden />
              Me
            </button>
          </li>
        </ul>
      </nav>
      <MeSheet open={meOpen} onOpenChange={setMeOpen} />
    </>
  );
}
