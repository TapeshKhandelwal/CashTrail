"use client";

import type { ReactNode } from "react";

import { useSession } from "@/components/providers/session-provider";
import { InstallPrompt } from "@/components/pwa/install-prompt";
import { OfflineBanner } from "@/components/pwa/offline-banner";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

import { AppHeader } from "./app-header";
import { AppSidebar } from "./app-sidebar";
import { BottomTabBar } from "./bottom-tab-bar";
import { CommandMenuProvider } from "./command-menu";
import { SessionExpiryWatcher } from "./session-expiry-watcher";
import { MAIN_CONTENT_ID, SkipLink } from "./skip-link";
import { TopProgress } from "./top-progress";

/**
 * Authenticated chrome: sidebar from md up (a sheet behind the menu button on phones), a sticky
 * top bar, and for agents a bottom tab bar on phones. Desk content is a 1200px column; agent
 * content is a 560px column at every width.
 */
export function AppShell({ defaultSidebarOpen, children }: { defaultSidebarOpen: boolean; children: ReactNode }) {
  const user = useSession();
  const isAgent = user.role === "AGENT";

  return (
    <CommandMenuProvider>
      <SkipLink />
      <TopProgress />
      <SessionExpiryWatcher />
      <SidebarProvider defaultOpen={defaultSidebarOpen}>
        <AppSidebar />
        <SidebarInset className="min-w-0 bg-paper">
          <AppHeader />
          <OfflineBanner />
          <main
            id={MAIN_CONTENT_ID}
            tabIndex={-1}
            className={cn(
              "mx-auto w-full flex-1 px-4 pt-6 pb-16 text-[14.5px] outline-none sm:px-6 lg:px-8 lg:pt-9",
              isAgent ? "max-w-[560px] max-md:pb-[calc(env(safe-area-inset-bottom)+7rem)] lg:max-w-[1180px]" : "max-w-[1264px]",
            )}
          >
            {children}
          </main>
        </SidebarInset>
      </SidebarProvider>
      {isAgent && <BottomTabBar />}
      <InstallPrompt />
    </CommandMenuProvider>
  );
}
