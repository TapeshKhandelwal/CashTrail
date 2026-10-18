"use client";

import { useQuery } from "@tanstack/react-query";
import { Landmark, Loader2, Plus, Smartphone } from "lucide-react";
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
import { bankAccountQueries, useCreateBankAccount, useUpdateBankAccount } from "@/features/deposits/api";
import { cn } from "@/lib/utils";
import type { BankAccount } from "@/types/domain";

export function BankAccountsAdmin() {
  const accounts = useQuery(bankAccountQueries.list({ page_size: 100 }));
  const [editing, setEditing] = useState<BankAccount | "new" | null>(null);

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Bank accounts"
        description="Company accounts that branches deposit into, and the account the payment gateway settles to. Only the last four digits are stored."
        actions={
          <Button onClick={() => setEditing("new")}>
            <Plus data-icon="inline-start" />
            Add account
          </Button>
        }
      />
      {accounts.isPending ? (
        <CardListSkeleton count={3} />
      ) : accounts.isError ? (
        <ErrorState error={accounts.error} onRetry={() => void accounts.refetch()} bordered />
      ) : accounts.data.results.length === 0 ? (
        <EmptyState bordered title="No accounts yet." />
      ) : (
        <ul className="rows-enter grid-ruled sm:grid-cols-2 md:max-lg:grid-cols-1">
          {accounts.data.results.map((account) => {
            const Icon = account.is_gateway ? Smartphone : Landmark;
            return (
              <li key={account.id}>
                <button
                  type="button"
                  onClick={() => setEditing(account)}
                  className={cn("flex h-full w-full items-start gap-4 bg-raised p-5 text-left transition-colors hover:bg-sunk/50", !account.is_active && "opacity-60")}
                >
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg border border-rule bg-sunk text-dim">
                    <Icon className="size-4.5" strokeWidth={1.5} />
                  </span>
                  <span className="flex min-w-0 flex-col gap-1">
                    <span className="text-[15px] text-ink">{account.bank_name}</span>
                    <span className="text-[13px] text-dim">{account.account_name}</span>
                    <span className="font-mono text-[12px] text-faint">
                      {account.masked_account_number}
                      {account.ifsc && ` · ${account.ifsc}`}
                    </span>
                    <span className="mt-1 text-[12px] text-faint">
                      {account.is_gateway ? "Gateway settlement account" : "Branch deposits"}
                      {!account.is_active && " · Inactive"}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {editing && <AccountDialog key={editing === "new" ? "new" : editing.id} existing={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}

function AccountDialog({ existing, onClose }: { existing: BankAccount | null; onClose: () => void }) {
  const [bank, setBank] = useState(existing?.bank_name ?? "");
  const [name, setName] = useState(existing?.account_name ?? "");
  const [number, setNumber] = useState("");
  const [ifsc, setIfsc] = useState(existing?.ifsc ?? "");
  const [gateway, setGateway] = useState(existing?.is_gateway ?? false);
  const [active, setActive] = useState(existing?.is_active ?? true);
  const create = useCreateBankAccount({ onSuccess: onClose });
  const update = useUpdateBankAccount({ onSuccess: onClose });
  const pending = create.isPending || update.isPending;
  const ifscValid = ifsc === "" || /^[A-Z]{4}0[A-Z0-9]{6}$/.test(ifsc);
  const ready = bank.trim().length >= 2 && name.trim().length >= 2 && ifscValid && (existing !== null || /^\d{6,18}$/.test(number));

  return (
    <ResponsiveDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={existing ? `${existing.bank_name} ${existing.masked_account_number}` : "Add a bank account"}
      description={existing ? "The account number cannot be changed; add a new account instead." : "The full number is used once to keep its last four digits."}
      footer={
        <Button
          disabled={!ready || pending}
          onClick={() =>
            existing
              ? update.mutate({ id: existing.id, bank_name: bank.trim(), account_name: name.trim(), ifsc: ifsc || undefined, is_gateway: gateway, is_active: active })
              : create.mutate({ bank_name: bank.trim(), account_name: name.trim(), account_number: number, ifsc: ifsc || undefined, is_gateway: gateway })
          }
        >
          {pending && <Loader2 className="animate-spin" />}
          {existing ? "Save changes" : "Add account"}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ba-bank">Bank</Label>
          <Input id="ba-bank" value={bank} onChange={(event) => setBank(event.target.value)} placeholder="HDFC Bank" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ba-name">Account name</Label>
          <Input id="ba-name" value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {!existing && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ba-number">Account number</Label>
              <Input id="ba-number" inputMode="numeric" value={number} onChange={(event) => setNumber(event.target.value.replace(/\D/g, ""))} className="font-mono" />
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ba-ifsc">IFSC</Label>
            <Input id="ba-ifsc" value={ifsc} maxLength={11} onChange={(event) => setIfsc(event.target.value.toUpperCase())} aria-invalid={!ifscValid || undefined} className="font-mono" placeholder="HDFC0001234" />
          </div>
        </div>
        <label className="flex items-center justify-between gap-4 border-t border-rule pt-4">
          <span className="flex flex-col gap-0.5">
            <span className="text-[13px] text-ink">Gateway settlement account</span>
            <span className="text-[12.5px] text-dim">UPI settlements are recorded against this account.</span>
          </span>
          <Switch checked={gateway} onCheckedChange={setGateway} />
        </label>
        {existing && (
          <label className="flex items-center justify-between gap-4">
            <span className="text-[13px] text-ink">Active</span>
            <Switch checked={active} onCheckedChange={setActive} />
          </label>
        )}
      </div>
    </ResponsiveDialog>
  );
}
