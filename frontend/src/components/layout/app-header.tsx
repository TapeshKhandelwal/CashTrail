"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Menu, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";

import { useSession } from "@/components/providers/session-provider";
import { Button } from "@/components/ui/button";
import { Kbd } from "@/components/ui/kbd";
import { SidebarTrigger, useSidebar } from "@/components/ui/sidebar";
import { ROLE_HOME } from "@/lib/auth/access";
import { TIME_ZONE } from "@/lib/dates";
import { activeNavItem, navItems, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

import { useCommandMenu } from "./command-menu";
import { usePageCrumb } from "./page-crumb";

/** Record references (RCT-…, SUB-…, DEP-…) set in mono so they fit a phone's top bar. */
const REFERENCE = /^[A-Z]{2,4}-[A-Z0-9]+(-[A-Z0-9]+)+$/;

interface Crumb {
  label: string;
  href?: string;
}

function useCrumbs(): { crumbs: Crumb[]; section: NavItem | undefined; isDetail: boolean; phoneTitle: string } {
  const user = useSession();
  const pathname = usePathname();
  const detailLabel = usePageCrumb();
  const home = navItems(user.role).find((item) => item.href === ROLE_HOME[user.role]);
  const section = activeNavItem(user.role, pathname);
  const isDetail = section ? pathname !== section.href : false;

  const crumbs: Crumb[] = [];
  if (home && section?.href !== home.href) crumbs.push({ label: home.title, href: home.href });
  if (section) crumbs.push({ label: section.title, href: isDetail ? section.href : undefined });
  if (isDetail) crumbs.push({ label: detailLabel ?? "Details" });
  // Phones show one name: the record when the page has named it, otherwise its section.
  const phoneTitle = isDetail ? (detailLabel ?? section?.title ?? "Details") : (crumbs.at(-1)?.label ?? "CashTrail");
  return { crumbs, section, isDetail, phoneTitle };
}

/**
 * Sticky top bar. Desktop: sidebar toggle, breadcrumb, IST date, search (⌘K) and refresh.
 * Phones: menu (desk roles) or back on detail screens, the page name, search and refresh.
 */
export function AppHeader() {
  const user = useSession();
  const isAgent = user.role === "AGENT";
  const { crumbs, section, isDetail, phoneTitle } = useCrumbs();

  return (
    <header
      data-print="hide"
      className="sticky top-0 z-30 border-b border-rule bg-paper/85 pt-safe backdrop-blur-md supports-[backdrop-filter]:bg-paper/75"
    >
      <div className="flex h-14 items-center gap-2 px-4 sm:px-5 lg:px-6">
        <SidebarTrigger className="text-dim hover:text-ink max-md:hidden" aria-label="Toggle sidebar (⌘B)" />
        <span aria-hidden className="mx-1 h-4 w-px bg-rule max-md:hidden" />

        {isDetail ? <BackButton fallback={section?.href ?? ROLE_HOME[user.role]} /> : !isAgent && <MobileMenuButton />}

        <Breadcrumbs crumbs={crumbs} className="max-md:hidden" />
        <p
          className={cn(
            "min-w-0 flex-1 truncate leading-none text-ink md:hidden",
            REFERENCE.test(phoneTitle)
              ? "font-mono text-[13px] tracking-[0.01em]"
              : "font-display text-[19px] tracking-[-0.015em]",
          )}
        >
          {phoneTitle}
        </p>

        <div className="ml-auto flex items-center gap-1">
          <IstDate className="mr-2 max-lg:hidden" />
          <SearchButton />
          <RefreshButton />
        </div>
      </div>
    </header>
  );
}

function Breadcrumbs({ crumbs, className }: { crumbs: Crumb[]; className?: string }) {
  return (
    <nav aria-label="Breadcrumb" className={cn("min-w-0 flex-1", className)}>
      <ol className="flex min-w-0 items-center gap-1.5 text-[13.5px]">
        {crumbs.map((crumb, index) => {
          const last = index === crumbs.length - 1;
          // Tablets with the sidebar open drop the home crumb so the record keeps its full name.
          const deep = crumbs.length > 2;
          return (
            <li
              key={`${crumb.label}-${index}`}
              className={cn("flex min-w-0 items-center gap-1.5", last && "shrink", deep && index === 0 && "max-lg:hidden")}
            >
              {index > 0 && (
                <span aria-hidden className={cn("text-rule-strong", deep && index === 1 && "max-lg:hidden")}>
                  /
                </span>
              )}
              {crumb.href && !last ? (
                <Link href={crumb.href} className="truncate rounded-sm text-dim transition-colors hover:text-ink">
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current="page" className={cn("truncate text-ink", last && crumbs.length > 2 && "font-mono text-[12.5px] tracking-[0.02em]")}>
                  {crumb.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Standalone iOS has no browser back, so every detail screen gets one. */
function BackButton({ fallback }: { fallback: string }) {
  const router = useRouter();
  const back = () => {
    if (window.history.length > 1) router.back();
    else router.push(fallback);
  };
  return (
    <Button variant="ghost" size="icon" className="-ml-1 text-ink md:hidden" onClick={back} aria-label="Back">
      <ArrowLeft className="size-5" />
    </Button>
  );
}

function MobileMenuButton() {
  const { setOpenMobile } = useSidebar();
  return (
    <Button variant="ghost" size="icon" className="-ml-1 text-ink md:hidden" onClick={() => setOpenMobile(true)} aria-label="Open navigation">
      <Menu className="size-5" />
    </Button>
  );
}

const istDate = new Intl.DateTimeFormat("en-IN", {
  timeZone: TIME_ZONE,
  weekday: "short",
  day: "2-digit",
  month: "short",
});
const noop = () => () => {};

/** "FRI 17 OCT · IST". Rendered after hydration so the server's clock never disagrees. */
function IstDate({ className }: { className?: string }) {
  const label = useSyncExternalStore(noop, () => istDate.format(new Date()).replace(",", ""), () => null);
  if (!label) return null;
  return (
    <span className={cn("font-mono text-[11px] tracking-[0.12em] whitespace-nowrap text-faint uppercase", className)}>
      {label} · IST
    </span>
  );
}

function SearchButton() {
  const openCommandMenu = useCommandMenu();
  return (
    <>
      <button
        type="button"
        onClick={() => openCommandMenu(true)}
        className="flex h-8 w-56 items-center gap-2 rounded-lg border border-rule bg-raised px-2.5 text-[13px] text-faint transition-colors outline-none hover:border-rule-strong hover:text-dim focus-visible:ring-3 focus-visible:ring-focus max-lg:hidden"
      >
        <Search className="size-3.5" aria-hidden />
        <span className="flex-1 text-left">Search or jump to…</span>
        <Kbd>⌘K</Kbd>
      </button>
      <Button variant="ghost" size="icon" onClick={() => openCommandMenu(true)} aria-label="Search" className="lg:hidden">
        <Search />
      </Button>
    </>
  );
}

function RefreshButton() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const refresh = async () => {
    setBusy(true);
    await queryClient.refetchQueries({ type: "active" });
    setBusy(false);
  };
  return (
    <Button variant="ghost" size="icon" onClick={refresh} aria-label="Refresh data" aria-busy={busy || undefined}>
      <RefreshCw className={cn("transition-transform", busy && "animate-spin")} />
    </Button>
  );
}
