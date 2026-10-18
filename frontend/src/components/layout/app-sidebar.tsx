"use client";

import Link from "next/link";

import { LogoMark } from "@/components/brand/logo-mark";
import { LogoLockup } from "@/components/brand/logo";
import { useSession } from "@/components/providers/session-provider";
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, useSidebar } from "@/components/ui/sidebar";
import { ROLE_HOME } from "@/lib/auth/access";
import { NAV } from "@/lib/nav";

import { BranchChip } from "./branch-chip";
import { NavMain } from "./nav-main";
import { ThemeToggle } from "./theme-toggle";
import { NavUser } from "./user-menu";

/** 248px paper rail: lockup, grouped navigation, branch, account and theme. ⌘B collapses it. */
export function AppSidebar() {
  const user = useSession();
  const { setOpenMobile } = useSidebar();

  return (
    <Sidebar collapsible="icon" data-print="hide">
      <SidebarHeader className="h-14 justify-center border-b border-rule px-4 group-data-[collapsible=icon]:px-0">
        <Link
          href={ROLE_HOME[user.role]}
          onClick={() => setOpenMobile(false)}
          aria-label="CashTrail home"
          className="group/logo flex w-fit items-center rounded-md group-data-[collapsible=icon]:mx-auto"
        >
          <LogoLockup size="sm" className="group-data-[collapsible=icon]:hidden" />
          <LogoMark className="hidden size-5 group-data-[collapsible=icon]:block" />
        </Link>
      </SidebarHeader>
      <SidebarContent className="gap-0 px-2 py-3">
        <nav aria-label="Main">
          <NavMain groups={NAV[user.role]} />
        </nav>
      </SidebarContent>
      <SidebarFooter className="gap-2 border-t border-rule p-3 group-data-[collapsible=icon]:px-2">
        <BranchChip />
        <div className="flex items-center gap-1.5">
          <NavUser />
          <ThemeToggle className="group-data-[collapsible=icon]:hidden" />
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
