"use client";

import { m } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { transition } from "@/lib/motion";
import { isActive, type NavGroup } from "@/lib/nav";

import { useNavBadges } from "./use-nav-badges";

/**
 * Role navigation under mono group labels. The active item gets ink text on a brand tint with a
 * 2px brand rule that glides between items. Counts are plain mono numerals, never pills.
 */
export function NavMain({ groups }: { groups: NavGroup[] }) {
  const pathname = usePathname();
  const badges = useNavBadges();
  const { branch, canSwitch } = useBranchScope();
  const { setOpenMobile } = useSidebar();
  const withScope = (href: string) => (canSwitch && branch ? `${href}?branch=${branch}` : href);

  return groups.map((group) => (
    <SidebarGroup key={group.label} className="px-0 py-1.5">
      <SidebarGroupLabel className="eyebrow h-7 px-2.5 text-[10.5px] font-normal text-faint">
        {group.label}
      </SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu className="gap-px">
          {group.items.map((item) => {
            const active = isActive(item, pathname);
            const count = item.badge ? (badges[item.badge] ?? 0) : 0;
            return (
              <SidebarMenuItem key={item.href} className="relative">
                {active && (
                  <m.span
                    layoutId="nav-rail"
                    transition={transition.glide}
                    aria-hidden
                    className="absolute inset-y-1.5 left-0 z-10 w-0.5 rounded-full bg-brand"
                  />
                )}
                <SidebarMenuButton
                  asChild
                  isActive={active}
                  tooltip={item.title}
                  className="h-8 gap-2.5 rounded-md px-2.5 max-md:h-11 max-md:text-[14.5px] text-[13.5px] text-dim transition-colors hover:bg-sunk hover:text-ink data-active:bg-brand-tint data-active:font-medium data-active:text-ink [&_svg]:size-4 [&_svg]:stroke-[1.6]"
                >
                  <Link
                    href={withScope(item.href)}
                    aria-current={active ? "page" : undefined}
                    onClick={() => setOpenMobile(false)}
                  >
                    <item.icon aria-hidden />
                    <span>{item.title}</span>
                    {count > 0 && (
                      <span className="ml-auto font-mono text-[11px] text-faint tabular-nums group-data-[collapsible=icon]:hidden">
                        <span className="sr-only">, </span>
                        {count}
                      </span>
                    )}
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  ));
}
