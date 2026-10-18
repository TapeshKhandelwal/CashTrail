"use client";

import { Download, Keyboard, LogOut } from "lucide-react";
import { useState, type ReactNode } from "react";

import { useSession } from "@/components/providers/session-provider";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Kbd, KbdGroup } from "@/components/ui/kbd";
import { useLogout } from "@/features/auth/api";
import { ROLE_LABEL } from "@/lib/auth/access";
import { initials } from "@/lib/format";
import { requestInstallPrompt, useIsStandalone } from "@/lib/pwa";
import { cn } from "@/lib/utils";

const SHORTCUTS = [
  { keys: ["⌘", "K"], label: "Search and jump anywhere" },
  { keys: ["⌘", "B"], label: "Collapse or expand the sidebar" },
  { keys: ["Esc"], label: "Close dialogs and sheets" },
];

export function UserAvatar({ name, className }: { name: string; className?: string }) {
  return (
    <Avatar className={cn("size-8", className)}>
      <AvatarFallback className="bg-sunk font-mono text-[11px] tracking-[0.04em] text-ink">{initials(name)}</AvatarFallback>
    </Avatar>
  );
}

/** Account menu: install, shortcuts and sign out. `trigger` lets each surface render its own button. */
export function UserMenu({
  trigger,
  align = "end",
  side = "bottom",
}: {
  trigger: ReactNode;
  align?: "start" | "end";
  side?: "top" | "bottom";
}) {
  const user = useSession();
  const logout = useLogout();
  const standalone = useIsStandalone();
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const name = user.full_name || user.username;

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
        <DropdownMenuContent align={align} side={side} sideOffset={8} className="w-64">
          <DropdownMenuLabel className="flex flex-col gap-1 px-2 py-2 font-normal">
            <span className="truncate text-[13.5px] font-medium text-ink">{name}</span>
            <span className="truncate font-mono text-[11px] tracking-[0.04em] text-faint">
              {ROLE_LABEL[user.role]}
              {user.branch_code ? ` · ${user.branch_code}` : ""} · @{user.username}
            </span>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            {!standalone && (
              <DropdownMenuItem onSelect={requestInstallPrompt}>
                <Download />
                Install app
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => setShortcutsOpen(true)} className="max-md:hidden">
              <Keyboard />
              Keyboard shortcuts
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => logout.mutate()} disabled={logout.isPending}>
            <LogOut />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Keyboard shortcuts</DialogTitle>
            <DialogDescription>Everything in CashTrail is reachable from the keyboard.</DialogDescription>
          </DialogHeader>
          <ul className="flex flex-col divide-y divide-rule">
            {SHORTCUTS.map((shortcut) => (
              <li key={shortcut.label} className="flex items-center justify-between py-2.5 text-[13.5px]">
                {shortcut.label}
                <KbdGroup>
                  {shortcut.keys.map((key) => (
                    <Kbd key={key}>{key}</Kbd>
                  ))}
                </KbdGroup>
              </li>
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Sidebar footer trigger: avatar, name and role. */
export function NavUser() {
  const user = useSession();
  const name = user.full_name || user.username;
  return (
    <UserMenu
      align="start"
      side="top"
      trigger={
        <button
          type="button"
          className="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg p-1 text-left transition-colors outline-none hover:bg-sunk focus-visible:ring-3 focus-visible:ring-focus group-data-[collapsible=icon]:flex-none"
        >
          <UserAvatar name={name} />
          <span className="flex min-w-0 flex-1 flex-col group-data-[collapsible=icon]:hidden">
            <span className="truncate text-[13px] font-medium text-ink">{name}</span>
            <span className="truncate text-[11.5px] text-faint">{ROLE_LABEL[user.role]}</span>
          </span>
        </button>
      }
    />
  );
}
