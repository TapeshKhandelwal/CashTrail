"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { ResponsiveDialog } from "@/components/sheets/detail-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateCustomer, useUpdateCustomer } from "@/features/customers/api";
import { useBranchOptions, useAgentOptions } from "@/hooks/use-filter-options";
import { useSession } from "@/components/providers/session-provider";
import type { CustomerDetail, CustomerUpdateInput } from "@/types/domain";

const PHONE = /^[6-9]\d{9}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Contact {
  full_name: string;
  phone: string;
  email: string;
  address: string;
}

const BLANK: Contact = { full_name: "", phone: "", email: "", address: "" };

function contactOf(customer: CustomerDetail | undefined): Contact {
  if (!customer) return BLANK;
  return { full_name: customer.full_name, phone: customer.phone, email: customer.email, address: customer.address };
}

function FieldError({ messages }: { messages?: string[] }) {
  return messages?.[0] ? <p className="text-[12.5px] text-st-rejected-fg">{messages[0]}</p> : null;
}

/**
 * New customer: name, a 10-digit mobile, email and address, plus the branch (admins) and the
 * agent who will visit. With `customer` it edits that customer's contact details instead.
 */
export function CustomerFormDialog({
  open,
  onOpenChange,
  customer,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  customer?: CustomerDetail;
  onCreated?: (customer: CustomerDetail) => void;
}) {
  const user = useSession();
  const editing = customer !== undefined;
  const isAdmin = user.role === "ADMIN";
  const branches = useBranchOptions(isAdmin && !editing);
  const [branch, setBranch] = useState<string>(user.branch ? String(user.branch) : "");
  const agents = useAgentOptions(branch ? Number(branch) : undefined, !editing && branch !== "");
  const [contact, setContact] = useState<Contact>(() => contactOf(customer));
  const [agent, setAgent] = useState<string>("none");
  const [wasOpen, setWasOpen] = useState(open);
  const create = useCreateCustomer();
  const update = useUpdateCustomer();
  const mutation = editing ? update : create;

  // Each opening starts from the saved details (or a blank form).
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setContact(contactOf(customer));
  }

  const set = (field: keyof Contact) => (value: string) => setContact((previous) => ({ ...previous, [field]: value }));
  const phoneValid = PHONE.test(contact.phone);
  const emailValid = contact.email.trim() === "" || EMAIL.test(contact.email.trim());
  const fieldErrors = mutation.error?.fieldErrors ?? {};

  const trimmed: Contact = {
    full_name: contact.full_name.trim(),
    phone: contact.phone,
    email: contact.email.trim(),
    address: contact.address.trim(),
  };
  const changes: CustomerUpdateInput = {};
  if (customer) {
    for (const field of Object.keys(trimmed) as (keyof Contact)[]) {
      if (trimmed[field] !== customer[field]) changes[field] = trimmed[field];
    }
  }
  const ready =
    trimmed.full_name.length >= 2 &&
    phoneValid &&
    emailValid &&
    (editing ? Object.keys(changes).length > 0 : branch !== "");

  const reset = () => {
    setAgent("none");
    create.reset();
    update.reset();
  };
  const close = () => {
    reset();
    onOpenChange(false);
  };

  const submit = () => {
    if (customer) {
      update.mutate({ id: customer.id, ...changes }, { onSuccess: close });
      return;
    }
    create.mutate(
      {
        full_name: trimmed.full_name,
        phone: trimmed.phone,
        email: trimmed.email || undefined,
        address: trimmed.address || undefined,
        branch: isAdmin ? Number(branch) : undefined,
        assigned_agent: agent === "none" ? null : Number(agent),
      },
      {
        onSuccess: (created) => {
          close();
          onCreated?.(created);
        },
      },
    );
  };

  return (
    <ResponsiveDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset();
        onOpenChange(next);
      }}
      title={editing ? "Edit customer" : "New customer"}
      description={
        editing
          ? `Contact details for ${customer.customer_code}. The branch and loans stay as they are.`
          : "Customers are created in a branch and visited by one of its agents."
      }
      footer={
        <Button disabled={!ready || mutation.isPending} onClick={submit}>
          {mutation.isPending && <Loader2 className="animate-spin" />}
          {editing ? "Save changes" : "Add customer"}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="c-name">Full name</Label>
          <Input
            id="c-name"
            value={contact.full_name}
            onChange={(event) => set("full_name")(event.target.value)}
            aria-invalid={Boolean(fieldErrors.full_name) || undefined}
            autoComplete="off"
          />
          <FieldError messages={fieldErrors.full_name} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="c-phone">Mobile number</Label>
            <Input
              id="c-phone"
              inputMode="numeric"
              maxLength={10}
              value={contact.phone}
              onChange={(event) => set("phone")(event.target.value.replace(/\D/g, ""))}
              aria-invalid={(contact.phone !== "" && !phoneValid) || Boolean(fieldErrors.phone) || undefined}
              className="font-mono"
              placeholder="98XXXXXXXX"
            />
            <FieldError
              messages={fieldErrors.phone ?? (contact.phone.length === 10 && !phoneValid ? ["Enter a 10-digit Indian mobile number."] : undefined)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="c-email">
              Email <span className="font-normal text-faint">(optional)</span>
            </Label>
            <Input
              id="c-email"
              type="email"
              inputMode="email"
              autoComplete="off"
              value={contact.email}
              onChange={(event) => set("email")(event.target.value)}
              aria-invalid={!emailValid || Boolean(fieldErrors.email) || undefined}
            />
            <FieldError messages={fieldErrors.email ?? (emailValid ? undefined : ["Enter a valid email address."])} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="c-address">Address</Label>
          <Textarea
            id="c-address"
            rows={2}
            value={contact.address}
            onChange={(event) => set("address")(event.target.value)}
            aria-invalid={Boolean(fieldErrors.address) || undefined}
          />
          <FieldError messages={fieldErrors.address} />
        </div>
        {!editing && (
          <div className="grid gap-3 sm:grid-cols-2">
            {isAdmin && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="c-branch">Branch</Label>
                <Select value={branch} onValueChange={setBranch}>
                  <SelectTrigger id="c-branch" className="w-full">
                    <SelectValue placeholder="Choose" />
                  </SelectTrigger>
                  <SelectContent>
                    {branches.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FieldError messages={fieldErrors.branch} />
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="c-agent">Agent</Label>
              <Select value={agent} onValueChange={setAgent}>
                <SelectTrigger id="c-agent" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Assign later</SelectItem>
                  {agents.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldError messages={fieldErrors.assigned_agent} />
            </div>
          </div>
        )}
      </div>
    </ResponsiveDialog>
  );
}
