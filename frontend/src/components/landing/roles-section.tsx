import { Building2, HandCoins, Landmark, ShieldCheck, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const ROLES: { title: string; icon: LucideIcon; does: string[]; preview: ReactNode }[] = [
  {
    title: "Field agent",
    icon: HandCoins,
    does: ["Today's route, overdue first", "Receipt in seconds, cash or UPI", "Counts and hands over cash"],
    preview: (
      <MiniRows
        rows={[
          ["Savitha Nair", "₹5,325.79", "text-st-short-fg"],
          ["Venkatesh Iyer", "₹10,412.29", "text-ink"],
          ["Meena Krishnan", "₹15,585.60", "text-ink"],
        ]}
      />
    ),
  },
  {
    title: "Branch manager",
    icon: Building2,
    does: ["Counts each hand-over note by note", "Records shortages against the agent", "Banks counted cash on one slip"],
    preview: (
      <MiniRows
        rows={[
          ["SUB-…-005 · Ravi", "Awaiting count", "text-st-submitted-fg"],
          ["SUB-…-004 · Deepa", "Matches", "text-st-settled-fg"],
          ["SUB-…-003 · Imran", "₹1,500 short", "text-st-short-fg"],
        ]}
      />
    ),
  },
  {
    title: "Finance",
    icon: Landmark,
    does: ["Matches deposits to the statement", "Settles UPI net of fees and tax", "Exports every ledger as CSV"],
    preview: (
      <MiniRows
        rows={[
          ["DEP-BLR01 · HDFC", "Settled", "text-st-settled-fg"],
          ["DEP-MUM01 · ICICI", "2 days pending", "text-st-delayed-fg"],
          ["Gateway · UTR KKBK…", "₹8,505.05", "text-ink"],
        ]}
      />
    ),
  },
  {
    title: "Admin",
    icon: ShieldCheck,
    does: ["Branches, people, bank accounts", "Every branch's dashboard", "An audit log nobody can edit"],
    preview: (
      <MiniRows
        rows={[
          ["Submission approved", "Kavitha R.", "text-dim"],
          ["Deposit settled", "Priya R.", "text-dim"],
          ["Edit refused", "database", "text-st-rejected-fg"],
        ]}
      />
    ),
  },
];

function MiniRows({ rows }: { rows: [string, string, string][] }) {
  return (
    <ul className="divide-y divide-rule overflow-hidden rounded-lg border border-rule bg-paper text-[11.5px]">
      {rows.map(([left, right, tone]) => (
        <li key={left} className="flex items-center justify-between gap-3 px-3 py-2">
          <span className="truncate text-ink">{left}</span>
          <span className={cn("shrink-0 tabular-nums", tone)}>{right}</span>
        </li>
      ))}
    </ul>
  );
}

export function RolesSection() {
  return (
    <div className="stagger mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {ROLES.map((role) => {
        const Icon = role.icon;
        return (
          <article key={role.title} className="flex flex-col gap-5 rounded-2xl border border-rule bg-raised p-5 transition-shadow duration-300 hover:shadow-[0_24px_48px_-28px_rgb(18_20_23/0.35)]">
            <div className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-lg border border-rule bg-sunk text-dim">
                <Icon className="size-4" strokeWidth={1.75} />
              </span>
              <h3 className="font-display text-[21px] leading-tight text-ink">{role.title}</h3>
            </div>
            {role.preview}
            <ul className="mt-auto flex flex-col gap-2 text-[13.5px] text-dim">
              {role.does.map((item) => (
                <li key={item} className="flex gap-2.5">
                  <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-rule-strong" />
                  {item}
                </li>
              ))}
            </ul>
          </article>
        );
      })}
    </div>
  );
}
