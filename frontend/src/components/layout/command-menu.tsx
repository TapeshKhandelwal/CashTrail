"use client";

import { useQuery } from "@tanstack/react-query";
import { ReceiptText, Search, SendHorizontal, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { createContext, use, useEffect, useState, type ReactNode } from "react";

import { useSession } from "@/components/providers/session-provider";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { collectionQueries } from "@/features/collections/api";
import { customerQueries } from "@/features/customers/api";
import { submissionQueries } from "@/features/submissions/api";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { formatINR } from "@/lib/format";
import { NAV_ACTIONS, navItems } from "@/lib/nav";
import type { Role } from "@/types/domain";

/** Where search results open, per role (roles without a detail page don't search that entity). */
const RESULT_ROUTES: Record<Role, { customer?: string; receipt?: string; submission?: string }> = {
  AGENT: { customer: "/app/agent/customers", receipt: "/app/agent/receipts", submission: "/app/agent/handover/submissions" },
  BRANCH_MANAGER: { customer: "/app/branch/customers", receipt: "/app/branch/collections", submission: "/app/branch/submissions" },
  ADMIN: { customer: "/app/branch/customers", receipt: "/app/branch/collections", submission: "/app/branch/submissions" },
  FINANCE: {},
};

const CommandMenuContext = createContext<(open: boolean) => void>(() => {});

/** Opens the palette from anywhere (header search button). */
export const useCommandMenu = () => use(CommandMenuContext);

/** ⌘K palette: role navigation, quick actions and live search over customers, receipts and hand-overs. */
export function CommandMenuProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <CommandMenuContext value={setOpen}>
      {children}
      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title="Search CashTrail"
        description="Jump to a page or find a record"
        className="rounded-2xl! border border-rule shadow-float max-sm:top-[calc(env(safe-area-inset-top)+0.75rem)] sm:max-w-xl"
      >
        {open && (
          <Command>
            <CommandMenuBody onDone={() => setOpen(false)} />
          </Command>
        )}
      </CommandDialog>
    </CommandMenuContext>
  );
}

function CommandMenuBody({ onDone }: { onDone: () => void }) {
  const user = useSession();
  const router = useRouter();
  const [term, setTerm] = useState("");
  const search = useDebouncedValue(term.trim(), 300);
  const routes = RESULT_ROUTES[user.role];
  const searching = search.length >= 2;

  const isAgent = user.role === "AGENT";
  const routeCustomers = useQuery({
    ...customerQueries.agentRoute({ search, page_size: 5 }),
    enabled: searching && isAgent,
  });
  const deskCustomers = useQuery({
    ...customerQueries.list({ search, page_size: 5 }),
    enabled: searching && !isAgent && Boolean(routes.customer),
  });
  const customers = isAgent ? routeCustomers : deskCustomers;
  const receipts = useQuery({
    ...collectionQueries.list({ search, page_size: 5 }),
    enabled: searching && Boolean(routes.receipt),
  });
  const submissions = useQuery({
    ...submissionQueries.list({ search, page_size: 5 }),
    enabled: searching && Boolean(routes.submission),
  });

  const go = (href: string) => {
    onDone();
    router.push(href);
  };

  return (
    <>
      <CommandInput placeholder="Search pages, customers, receipts…" value={term} onValueChange={setTerm} />
      <CommandList>
        <CommandEmpty>{searching ? "No matches." : "Type to search."}</CommandEmpty>
        {searching && (
          <>
            {routes.customer && Boolean(customers.data?.results.length) && (
              <CommandGroup heading="Customers">
                {customers.data?.results.map((customer) => (
                  <CommandItem
                    key={`c-${customer.id}`}
                    value={`customer ${customer.full_name} ${customer.customer_code} ${customer.phone}`}
                    onSelect={() => go(`${routes.customer}/${customer.id}`)}
                  >
                    <UserRound />
                    <span>{customer.full_name}</span>
                    <span className="ml-auto font-mono text-[11px] text-faint">{customer.customer_code}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {routes.receipt && Boolean(receipts.data?.results.length) && (
              <CommandGroup heading="Receipts">
                {receipts.data?.results.map((receipt) => (
                  <CommandItem
                    key={`r-${receipt.id}`}
                    value={`receipt ${receipt.receipt_number} ${receipt.customer_name}`}
                    onSelect={() => go(`${routes.receipt}/${receipt.id}`)}
                  >
                    <ReceiptText />
                    <span className="font-mono text-[12px]">{receipt.receipt_number}</span>
                    <span className="truncate text-dim">{receipt.customer_name}</span>
                    <span className="ml-auto text-[12.5px] tabular-nums">{formatINR(receipt.amount)}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {routes.submission && Boolean(submissions.data?.results.length) && (
              <CommandGroup heading="Hand-overs">
                {submissions.data?.results.map((submission) => (
                  <CommandItem
                    key={`s-${submission.id}`}
                    value={`submission ${submission.submission_number} ${submission.agent_name}`}
                    onSelect={() => go(`${routes.submission}/${submission.id}`)}
                  >
                    <SendHorizontal />
                    <span className="font-mono text-[12px]">{submission.submission_number}</span>
                    <span className="truncate text-dim">{submission.agent_name}</span>
                    <span className="ml-auto text-[12.5px] tabular-nums">{formatINR(submission.declared_amount)}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            <CommandSeparator />
          </>
        )}
        <CommandGroup heading="Actions">
          {NAV_ACTIONS[user.role].map((action) => (
            <CommandItem key={action.href + action.title} value={`action ${action.title}`} onSelect={() => go(action.href)}>
              <action.icon />
              {action.title}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Navigate">
          {navItems(user.role).map((item) => (
            <CommandItem
              key={item.href + item.title}
              value={`page ${item.title} ${(item.keywords ?? []).join(" ")}`}
              onSelect={() => go(item.href)}
            >
              <item.icon />
              {item.title}
            </CommandItem>
          ))}
        </CommandGroup>
        {searching && (customers.isFetching || receipts.isFetching || submissions.isFetching) && (
          <div className="flex items-center gap-2 px-3 py-2 font-mono text-[11px] tracking-[0.08em] text-faint uppercase" role="status">
            <Search className="size-3.5 animate-pulse" aria-hidden /> Searching…
          </div>
        )}
      </CommandList>
    </>
  );
}
