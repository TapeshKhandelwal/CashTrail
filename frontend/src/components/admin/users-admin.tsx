"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { createColumns } from "@/components/data-table/data-table-features";
import { DataTable } from "@/components/data-table/data-table";
import { FilterBar } from "@/components/data-table/filter-bar";
import { PageHeader } from "@/components/layout/page-header";
import { FactList } from "@/components/layout/section-card";
import { DetailSheet, ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateUser, userQueries, useSetUserActive, useSetUserPassword } from "@/features/users/api";
import { useDataTableState, type FilterDef } from "@/hooks/use-data-table-state";
import { useIsMobile } from "@/hooks/use-mobile";
import { useBranchOptions } from "@/hooks/use-filter-options";
import { formatDateTime, formatRelative } from "@/lib/dates";
import { cn } from "@/lib/utils";
import { ROLES, type Role, type UserDetail } from "@/types/domain";

const ROLE_LABEL: Record<Role, string> = {
  AGENT: "Collection agent",
  BRANCH_MANAGER: "Branch manager",
  FINANCE: "Finance",
  ADMIN: "Admin",
};
const BRANCH_ROLES: Role[] = ["AGENT", "BRANCH_MANAGER"];

const col = createColumns<UserDetail>();
const COLUMNS = col.columns([
  col.accessor("full_name", {
    header: "Name",
    meta: { card: "title" },
    cell: ({ row }) => (
      <span className="flex flex-col">
        <span className={row.original.is_active ? "" : "text-faint line-through decoration-1"}>{row.original.full_name || row.original.username}</span>
        <span className="font-mono text-[11.5px] text-faint">{row.original.username}</span>
      </span>
    ),
  }),
  col.accessor("role", { header: "Role", cell: ({ getValue }) => ROLE_LABEL[getValue()] }),
  col.accessor("branch_code", {
    header: "Branch",
    cell: ({ getValue }) => <span className="font-mono text-[12px] text-dim">{getValue() ?? "All"}</span>,
  }),
  col.accessor("last_login", {
    header: "Last sign-in",
    cell: ({ getValue }) => <span className="text-dim">{getValue() ? formatRelative(getValue() as string) : "Never"}</span>,
  }),
  col.accessor("is_active", {
    header: "Status",
    meta: { card: "badge" },
    cell: ({ getValue }) => <ActiveDot active={getValue()} />,
  }),
]);

function ActiveDot({ active }: { active: boolean }) {
  return (
    <span className={cn("inline-flex shrink-0 items-center gap-1.5 text-[12.5px]", active ? "text-st-settled-fg" : "text-faint")}>
      <span className={cn("size-1.5 rounded-full", active ? "bg-st-settled" : "bg-rule-strong")} />
      {active ? "Active" : "Deactivated"}
    </span>
  );
}

/** Phone card: who, whether they can sign in, then role, branch and last sign-in on one line each. */
function UserCard({ user }: { user: UserDetail }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-3">
        <span className={cn("min-w-0 truncate font-medium text-ink", !user.is_active && "text-faint line-through decoration-1")}>
          {user.full_name || user.username}
        </span>
        <ActiveDot active={user.is_active} />
      </div>
      <span className="truncate font-mono text-[11.5px] text-faint">{user.username}</span>
      <span className="mt-1 truncate text-[13px] text-dim">
        {ROLE_LABEL[user.role]} · {user.branch_code ? <span className="font-mono text-[12px]">{user.branch_code}</span> : "All branches"}
      </span>
      <span className="text-[12.5px] text-faint">
        {user.last_login ? `Signed in ${formatRelative(user.last_login)}` : "Never signed in"}
      </span>
    </div>
  );
}

const FILTERS: FilterDef[] = [
  { type: "select", key: "role", label: "Role", options: ROLES.map((role) => ({ value: role, label: ROLE_LABEL[role] })) },
  { type: "select", key: "branch", label: "Branch", options: [] },
];

export function UsersAdmin() {
  const branches = useBranchOptions();
  const state = useDataTableState({ filters: FILTERS, defaultOrdering: "username" });
  const list = useQuery(userQueries.list(state.query));
  const [selected, setSelected] = useState<UserDetail | null>(null);
  const [creating, setCreating] = useState(false);
  const filters = FILTERS.map((filter) => (filter.type === "select" && filter.key === "branch" ? { ...filter, options: branches } : filter));

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Everyone who can sign in, their role and branch. Deactivating someone ends their sessions at once."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus data-icon="inline-start" />
            New user
          </Button>
        }
      />
      <DataTable
        caption="Users"
        columns={COLUMNS}
        data={list.data?.results}
        rowCount={list.data?.count}
        state={state}
        isLoading={list.isFetching}
        error={list.error}
        onRetry={() => void list.refetch()}
        onRowClick={setSelected}
        renderCard={(user) => <UserCard user={user} />}
        toolbar={<FilterBar state={{ ...state, filters }} searchPlaceholder="Name or username" />}
      />
      <UserSheet user={selected} onClose={() => setSelected(null)} />
      {creating && <CreateUserDialog onClose={() => setCreating(false)} />}
    </>
  );
}

function UserSheet({ user, onClose }: { user: UserDetail | null; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const setActive = useSetUserActive({ onSuccess: onClose });
  const setPw = useSetUserPassword({ onSuccess: () => setPassword("") });
  // On phones a content-height sheet keeps "Deactivate" in view; a half-height detail sheet would hide it.
  const Overlay = useIsMobile() ? ResponsiveDialog : DetailSheet;

  return (
    <Overlay
      open={user !== null}
      onOpenChange={(open) => !open && onClose()}
      title={user ? user.full_name || user.username : ""}
      description={user ? `${ROLE_LABEL[user.role]}${user.branch_code ? ` · ${user.branch_code}` : ""}` : undefined}
      footer={
        user && (
          <Button
            variant={user.is_active ? "destructive" : "default"}
            disabled={setActive.isPending}
            onClick={() => setActive.mutate({ id: user.id, active: !user.is_active })}
          >
            {setActive.isPending && <Loader2 className="animate-spin" />}
            {user.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        )
      }
    >
      {user && (
        <div className="flex flex-col gap-6">
          <FactList
            columns={2}
            className="max-sm:grid-cols-2 max-sm:[&>:last-child]:col-span-2 max-sm:[&>:nth-child(3)]:col-span-2"
            items={[
              ["Username", <span key="u" className="font-mono">{user.username}</span>],
              ["Phone", user.phone || "—"],
              ["Email", user.email || "—"],
              ["Joined", formatDateTime(user.date_joined)],
              ["Last sign-in", user.last_login ? formatDateTime(user.last_login) : "Never"],
              ["Status", user.is_active ? "Active" : "Deactivated"],
            ]}
          />
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-password">Set a new password</Label>
            <div className="flex gap-2">
              <Input id="new-password" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
              <Button variant="outline" disabled={password.length < 8 || setPw.isPending} onClick={() => setPw.mutate({ id: user.id, password })}>
                Set
              </Button>
            </div>
            <p className="text-[12.5px] text-dim">At least 8 characters. Their current sessions end immediately.</p>
          </div>
        </div>
      )}
    </Overlay>
  );
}

function CreateUserDialog({ onClose }: { onClose: () => void }) {
  const branches = useBranchOptions();
  const [form, setForm] = useState({ username: "", first_name: "", last_name: "", phone: "", password: "", role: "AGENT" as Role, branch: "" });
  const create = useCreateUser({ onSuccess: onClose });
  const needsBranch = BRANCH_ROLES.includes(form.role);
  const errors = create.error?.fieldErrors ?? {};
  const ready =
    /^[a-z0-9._]{3,}$/.test(form.username) && form.first_name.trim().length >= 2 && form.password.length >= 8 && (!needsBranch || form.branch !== "");
  const set = (key: keyof typeof form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));

  return (
    <ResponsiveDialog
      open
      onOpenChange={(open) => !open && onClose()}
      title="New user"
      description="Agents and branch managers belong to one branch; finance and admins see every branch."
      footer={
        <Button
          disabled={!ready || create.isPending}
          onClick={() =>
            create.mutate({
              username: form.username,
              password: form.password,
              first_name: form.first_name.trim(),
              last_name: form.last_name.trim() || undefined,
              phone: form.phone || undefined,
              role: form.role,
              branch: needsBranch ? Number(form.branch) : null,
            })
          }
        >
          {create.isPending && <Loader2 className="animate-spin" />}
          Create user
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name" id="u-first" value={form.first_name} onChange={set("first_name")} error={errors.first_name?.[0]} />
          <Field label="Last name" id="u-last" value={form.last_name} onChange={set("last_name")} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Username" id="u-username" value={form.username} onChange={(value) => set("username")(value.toLowerCase())} mono error={errors.username?.[0]} />
          <Field label="Phone" id="u-phone" value={form.phone} onChange={(value) => set("phone")(value.replace(/\D/g, "").slice(0, 10))} mono />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="u-role">Role</Label>
            <Select value={form.role} onValueChange={set("role")}>
              <SelectTrigger id="u-role" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((role) => (
                  <SelectItem key={role} value={role}>
                    {ROLE_LABEL[role]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="u-branch">Branch</Label>
            <Select value={needsBranch ? form.branch : ""} onValueChange={set("branch")} disabled={!needsBranch}>
              <SelectTrigger id="u-branch" className="w-full">
                <SelectValue placeholder={needsBranch ? "Choose" : "All branches"} />
              </SelectTrigger>
              <SelectContent>
                {branches.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Field label="Temporary password" id="u-password" type="password" value={form.password} onChange={set("password")} error={errors.password?.[0]} hint="At least 8 characters; share it privately." />
      </div>
    </ResponsiveDialog>
  );
}

function Field({
  label,
  id,
  value,
  onChange,
  error,
  hint,
  mono,
  type = "text",
}: {
  label: string;
  id: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: string;
  mono?: boolean;
  type?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error) || undefined} className={mono ? "font-mono" : undefined} autoComplete="off" />
      {error ? <p className="text-[12.5px] text-st-rejected-fg">{error}</p> : hint ? <p className="text-[12.5px] text-dim">{hint}</p> : null}
    </div>
  );
}
