"use client";

import { ChevronRight, Download, LogOut, ReceiptText, SendHorizontal } from "lucide-react";
import Link from "next/link";

import { useSession } from "@/components/providers/session-provider";
import { BottomSheet } from "@/components/sheets/bottom-sheet";
import { useLogout } from "@/features/auth/api";
import { ROLE_LABEL } from "@/lib/auth/access";
import { requestInstallPrompt, useIsStandalone } from "@/lib/pwa";

import { ThemeToggle } from "./theme-toggle";

const LINKS = [
  { title: "History", description: "Every collection you've recorded", href: "/app/agent/collections", icon: ReceiptText },
  { title: "Hand-overs", description: "Every hand-over and how it was counted", href: "/app/agent/handover/submissions", icon: SendHorizontal },
];

const ROW =
  "flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left transition-colors outline-none hover:bg-sunk focus-visible:bg-sunk";

/** The agent's "Me" tab: account, history, theme, install and sign out. */
export function MeSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const user = useSession();
  const logout = useLogout();
  const standalone = useIsStandalone();
  const close = () => onOpenChange(false);

  return (
    <BottomSheet
      open={open}
      onOpenChange={onOpenChange}
      title={user.full_name || user.username}
      description={
        <span className="font-mono text-[11px] tracking-[0.08em] uppercase">
          {ROLE_LABEL[user.role]}
          {user.branch_code ? ` · ${user.branch_code}` : ""}
          {user.branch_name ? ` · ${user.branch_name}` : ""}
        </span>
      }
    >
      <div className="flex flex-col gap-4 pb-2">
        <ul className="overflow-hidden rounded-xl border border-rule divide-y divide-rule">
          {LINKS.map((link) => (
            <li key={link.href}>
              <Link href={link.href} onClick={close} className={ROW}>
                <link.icon className="size-[18px] text-dim" strokeWidth={1.6} aria-hidden />
                <span className="flex flex-1 flex-col">
                  <span className="text-[14.5px] text-ink">{link.title}</span>
                  <span className="text-[12.5px] text-dim">{link.description}</span>
                </span>
                <ChevronRight className="size-4 text-faint" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>

        <div className="flex items-center justify-between rounded-xl border border-rule px-4 py-3">
          <span className="text-[14.5px] text-ink">Appearance</span>
          <ThemeToggle />
        </div>

        <ul className="overflow-hidden rounded-xl border border-rule divide-y divide-rule">
          {!standalone && (
            <li>
              <button
                type="button"
                className={ROW}
                onClick={() => {
                  close();
                  requestInstallPrompt();
                }}
              >
                <Download className="size-[18px] text-dim" strokeWidth={1.6} aria-hidden />
                <span className="flex-1 text-[14.5px] text-ink">Install app</span>
              </button>
            </li>
          )}
          <li>
            <button type="button" className={ROW} onClick={() => logout.mutate()} disabled={logout.isPending}>
              <LogOut className="size-[18px] text-st-rejected-fg" strokeWidth={1.6} aria-hidden />
              <span className="flex-1 text-[14.5px] text-st-rejected-fg">Sign out</span>
            </button>
          </li>
        </ul>
      </div>
    </BottomSheet>
  );
}
