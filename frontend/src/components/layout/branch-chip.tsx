"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, ChevronsUpDown } from "lucide-react";

import { useSession } from "@/components/providers/session-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { branchQueries } from "@/features/branches/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import { cn } from "@/lib/utils";

const CHIP =
  "flex h-9 w-full min-w-0 items-center gap-2 rounded-lg border border-rule bg-raised px-2.5 text-left group-data-[collapsible=icon]:hidden";

/**
 * Where the signed-in person is looking, in mono: `BLR01 · Bengaluru Central`. Branch roles
 * see their own branch; admin and finance pick one (or all) and the choice rides in `?branch=`.
 */
export function BranchChip() {
  const user = useSession();
  const { branch, canSwitch, setBranch } = useBranchScope();
  const { data: branches } = useQuery({ ...branchQueries.options(), enabled: canSwitch });

  if (!canSwitch) {
    if (!user.branch_code) return null;
    return (
      <div className={CHIP}>
        <BranchLabel code={user.branch_code} name={user.branch_name} />
      </div>
    );
  }

  const current = branches?.find((item) => item.id === branch);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={cn(CHIP, "transition-colors hover:border-rule-strong focus-visible:ring-3 focus-visible:ring-focus focus-visible:outline-none")}>
        {current ? (
          <BranchLabel code={current.code} name={current.name} />
        ) : (
          <span className="flex min-w-0 flex-1 items-center gap-2">
            <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-rule-strong" />
            <span className="font-mono text-[11px] tracking-[0.08em] text-ink uppercase">All branches</span>
          </span>
        )}
        <ChevronsUpDown className="size-3.5 shrink-0 text-faint" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-(--radix-dropdown-menu-trigger-width) min-w-60">
        <DropdownMenuLabel className="eyebrow">Viewing</DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => setBranch(null)}>
          <Check className={cn(branch !== null && "invisible")} />
          All branches
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {branches?.map((item) => (
          <DropdownMenuItem key={item.id} onSelect={() => setBranch(item.id)}>
            <Check className={cn(branch !== item.id && "invisible")} />
            <span className="font-mono text-[11px] tracking-[0.06em] text-faint">{item.code}</span>
            <span className="truncate">{item.name}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function BranchLabel({ code, name }: { code: string; name: string | null | undefined }) {
  return (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-brand" />
      <span className="font-mono text-[11px] tracking-[0.08em] text-ink">{code}</span>
      {name && (
        <>
          <span aria-hidden className="text-rule-strong">·</span>
          <span className="truncate text-[12.5px] text-dim">{name}</span>
        </>
      )}
    </span>
  );
}
