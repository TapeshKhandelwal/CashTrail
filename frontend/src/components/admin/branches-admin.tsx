"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { branchQueries, useCreateBranch, useUpdateBranch } from "@/features/branches/api";
import { countOf } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Branch } from "@/types/domain";

export function BranchesAdmin() {
  const branches = useQuery(branchQueries.list({ page_size: 100, ordering: "code" }));
  const [editing, setEditing] = useState<Branch | "new" | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Branches"
        description="Where cash is counted and banked. Agents and managers belong to exactly one branch."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus data-icon="inline-start" />
            New branch
          </Button>
        }
      />
      {branches.isPending ? (
        <CardListSkeleton count={3} />
      ) : branches.isError ? (
        <ErrorState error={branches.error} onRetry={() => void branches.refetch()} bordered />
      ) : branches.data.results.length === 0 ? (
        <EmptyState bordered title="No branches yet." />
      ) : (
        <ul className="rows-enter grid-ruled sm:grid-cols-2 xl:grid-cols-3">
          {branches.data.results.map((branch) => (
            <li key={branch.id}>
              <button
                type="button"
                onClick={() => setEditing(branch)}
                className="flex h-full w-full flex-col gap-4 bg-raised p-5 text-left transition-colors hover:bg-sunk/50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-col gap-1">
                    <span className="font-mono text-[12px] tracking-[0.06em] text-faint">{branch.code}</span>
                    <span className="font-display text-[21px] leading-tight text-ink">{branch.name}</span>
                    <span className="text-[13px] text-dim">{branch.city}</span>
                  </div>
                  <span className={cn("inline-flex items-center gap-1.5 text-[12px]", branch.is_active ? "text-st-settled-fg" : "text-faint")}>
                    <span className={cn("size-1.5 rounded-full", branch.is_active ? "bg-st-settled" : "bg-rule-strong")} />
                    {branch.is_active ? "Active" : "Closed"}
                  </span>
                </div>
                <p className="mt-auto text-[12.5px] text-dim">
                  {countOf(branch.agent_count, "agent")} · {countOf(branch.customer_count, "customer")}
                </p>
              </button>
            </li>
          ))}
        </ul>
      )}
      <BranchDialog branch={editing} onClose={() => setEditing(null)} />
    </>
  );
}

function BranchDialog({ branch, onClose }: { branch: Branch | "new" | null; onClose: () => void }) {
  const existing = branch && branch !== "new" ? branch : null;
  const key = branch === "new" ? "new" : (existing?.id ?? "none");
  return branch ? <BranchForm key={key} existing={existing} onClose={onClose} /> : null;
}

function BranchForm({ existing, onClose }: { existing: Branch | null; onClose: () => void }) {
  const [code, setCode] = useState(existing?.code ?? "");
  const [name, setName] = useState(existing?.name ?? "");
  const [city, setCity] = useState(existing?.city ?? "");
  const [address, setAddress] = useState(existing?.address ?? "");
  const [active, setActive] = useState(existing?.is_active ?? true);
  const create = useCreateBranch({ onSuccess: onClose });
  const update = useUpdateBranch({ onSuccess: onClose });
  const pending = create.isPending || update.isPending;
  const ready = /^[A-Z]{3}\d{2}$/.test(code) && name.trim().length >= 2 && city.trim().length >= 2;

  return (
    <ResponsiveDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={existing ? `Edit ${existing.code}` : "New branch"}
      description={existing ? "The code is permanent; it appears on every receipt and deposit." : "Codes look like BLR01: three letters and two digits."}
      footer={
        <Button
          disabled={!ready || pending}
          onClick={() =>
            existing
              ? update.mutate({ id: existing.id, name: name.trim(), city: city.trim(), address: address.trim(), is_active: active })
              : create.mutate({ code, name: name.trim(), city: city.trim(), address: address.trim() || undefined })
          }
        >
          {pending && <Loader2 className="animate-spin" />}
          {existing ? "Save changes" : "Create branch"}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="b-code">Code</Label>
            <Input id="b-code" value={code} disabled={Boolean(existing)} maxLength={5} onChange={(event) => setCode(event.target.value.toUpperCase())} className="font-mono" placeholder="PUN01" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="b-name">Name</Label>
            <Input id="b-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="Pune Camp" />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="b-city">City</Label>
          <Input id="b-city" value={city} onChange={(event) => setCity(event.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="b-address">Address</Label>
          <Textarea id="b-address" rows={2} value={address} onChange={(event) => setAddress(event.target.value)} />
        </div>
        {existing && (
          <label className="flex items-center justify-between gap-4 border-t border-rule pt-4">
            <span className="flex flex-col gap-0.5">
              <span className="text-[13px] text-ink">Open</span>
              <span className="text-[12.5px] text-dim">A branch with active customers cannot be closed.</span>
            </span>
            <Switch checked={active} onCheckedChange={setActive} />
          </label>
        )}
      </div>
    </ResponsiveDialog>
  );
}
