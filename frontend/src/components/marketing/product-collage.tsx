import { Check, Lock } from "lucide-react";

import { LogoMark } from "@/components/brand/logo-mark";
import { cn } from "@/lib/utils";

/**
 * The product, shown rather than described: an agent's receipt on a phone, a branch cash count
 * that came up short, a settled deposit and a live total, floating over a ruled ledger page.
 * Pure markup, so it is crisp at any size, themes with the app and costs no image bytes.
 */
export function ProductCollage({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("relative isolate select-none", className)}>
      <div className="absolute inset-0 -z-10 overflow-hidden rounded-[28px] border border-rule bg-sunk">
        <div className="absolute inset-0 bg-[repeating-linear-gradient(to_bottom,transparent_0_33px,color-mix(in_oklab,var(--rule)_80%,transparent)_33px_34px)] [mask-image:radial-gradient(120%_90%_at_60%_40%,black,transparent)]" />
        <div className="absolute inset-y-0 left-[9%] w-px bg-st-rejected/20" />
        <div className="absolute -top-1/4 -right-1/4 size-[85%] rounded-full bg-brand/14 blur-3xl" />
        <div className="absolute -bottom-1/3 -left-1/4 size-[70%] rounded-full bg-st-collected/12 blur-3xl" />
        <div className="grain absolute inset-0 opacity-[0.35] mix-blend-multiply dark:mix-blend-overlay" />
      </div>

      <PhoneReceipt className="float-a absolute top-[5%] left-[7%] w-[40%] max-w-[236px] max-sm:top-[4%] max-sm:left-[4%] max-sm:w-[54%]" />
      <CountCard className="float-b absolute top-[12%] right-[5%] w-[50%] max-w-[300px] max-sm:top-auto max-sm:right-[4%] max-sm:bottom-[4%] max-sm:w-[62%]" />
      <SettledCard className="float-c absolute right-[8%] bottom-[9%] w-[54%] max-w-[318px] max-sm:hidden" />
      <TotalChip className="float-b absolute bottom-[5%] left-[3%] w-[33%] max-w-[190px] max-sm:top-[7%] max-sm:right-[4%] max-sm:bottom-auto max-sm:left-auto max-sm:w-[40%]" />
    </div>
  );
}

const CARD = "rounded-2xl border border-rule bg-raised shadow-[0_30px_60px_-30px_rgb(18_20_23/0.35),0_2px_6px_rgb(18_20_23/0.06)]";

function PhoneReceipt({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-[34px] border border-ink/10 bg-ink p-[7px] shadow-[0_40px_80px_-30px_rgb(18_20_23/0.55)] dark:border-white/10 dark:bg-[#050606]", className)}>
      <div className="relative overflow-hidden rounded-[28px] bg-paper">
        <div className="mx-auto mt-2 h-[18px] w-[34%] rounded-full bg-ink dark:bg-[#050606]" />
        <div className="flex flex-col gap-3 px-4 pt-4 pb-5 max-sm:px-3">
          <div className="flex items-center gap-2">
            <span className="grid size-7 place-items-center rounded-full border border-brand/30 text-brand">
              <Check className="size-3.5" strokeWidth={2.5} />
            </span>
            <span className="font-display text-[15px] leading-tight text-ink">Receipt recorded.</span>
          </div>
          <div className="perforated -mx-1 bg-raised px-3.5 pt-4 pb-5 max-sm:px-3 shadow-[0_8px_20px_-12px_rgb(18_20_23/0.25)]">
            <div className="flex items-center justify-between">
              <LogoMark className="size-4 text-brand" />
              <span className="flex items-center gap-1 text-[9px] font-medium text-st-collected-fg">
                <span className="size-1 rounded-full bg-st-collected" />
                Collected
              </span>
            </div>
            <p className="mt-3 font-mono text-[8.5px] text-faint">RCT-BLR01-20261017-00412</p>
            <p className="mt-2 text-[24px] leading-none max-sm:text-[21px] font-medium tracking-[-0.02em] text-ink tabular-nums">
              <span className="mr-0.5 text-[0.6em] font-normal text-dim">₹</span>2,450.00
            </p>
            <p className="mt-1.5 text-[8.5px] leading-snug text-dim">Two thousand four hundred fifty rupees only</p>
            <div className="mt-3 flex flex-col gap-1.5 border-t border-dashed border-rule-strong pt-3 text-[9px]">
              {[
                ["Customer", "Sunita Rao"],
                ["Loan", "LN-BLR01-000045"],
                ["Balance after", "₹24,108.40"],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between">
                  <span className="text-dim">{label}</span>
                  <span className="text-ink">{value}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-1 px-1">
            {["bg-st-collected", "bg-rule-strong", "bg-rule-strong", "bg-rule-strong", "bg-rule-strong"].map((tone, index) => (
              <span key={index} className={cn("h-1 flex-1 rounded-full", tone)} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function CountCard({ className }: { className?: string }) {
  return (
    <div className={cn(CARD, "p-4", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-0 truncate font-mono text-[9px] tracking-[0.14em] text-faint uppercase">Count · SUB-MUM01-003</span>
        <span className="shrink-0 rounded-full bg-st-short/10 px-1.5 py-0.5 text-[9px] font-medium whitespace-nowrap text-st-short-fg">₹1,500 short</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        {[
          ["Receipted", "50,000.00", "text-ink"],
          ["Counted", "48,500.00", "text-ink"],
        ].map(([label, value, tone]) => (
          <div key={label} className="flex flex-col gap-0.5">
            <span className="text-[9.5px] text-dim">{label}</span>
            <span className={cn("text-[17px] font-medium tracking-[-0.02em] tabular-nums max-sm:text-[15px]", tone)}>
              <span className="mr-0.5 text-[0.65em] font-normal text-dim">₹</span>
              {value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-sunk">
        <div className="h-full w-[97%] rounded-full bg-st-short" />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-1.5">
        {[
          ["₹500", "85"],
          ["₹200", "20"],
          ["₹100", "20"],
        ].map(([note, count]) => (
          <div key={note} className="rounded-lg border border-rule px-2 py-1.5">
            <p className="font-mono text-[9px] text-faint">{note}</p>
            <p className="text-[11px] text-ink tabular-nums">× {count}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SettledCard({ className }: { className?: string }) {
  return (
    <div className={cn(CARD, "overflow-hidden", className)}>
      <div className="flex items-center justify-between border-b border-rule px-4 py-2.5">
        <span className="font-mono text-[9px] tracking-[0.14em] text-faint uppercase">DEP-DEL01-20261016-001</span>
        <span className="flex items-center gap-1 text-[9px] font-medium text-st-settled-fg">
          <Lock className="size-2.5" />
          Settled
        </span>
      </div>
      <div className="grid grid-cols-3 divide-x divide-rule">
        {[
          ["Counted", "3,12,400", "bg-st-received"],
          ["Deposited", "3,12,400", "bg-st-deposited"],
          ["Credited", "3,12,400", "bg-st-settled"],
        ].map(([label, value, dot]) => (
          <div key={label} className="flex flex-col gap-1 px-3 py-3">
            <span className="flex items-center gap-1 text-[9px] text-dim">
              <span className={cn("size-1 rounded-full", dot)} />
              {label}
            </span>
            <span className="text-[13px] font-medium tracking-[-0.01em] text-ink tabular-nums">₹{value}</span>
          </div>
        ))}
      </div>
      <p className="bg-st-settled/8 px-4 py-2 text-[9.5px] text-st-settled-fg">Reconciled end to end · HDFC ••4821</p>
    </div>
  );
}

function TotalChip({ className }: { className?: string }) {
  return (
    <div className={cn(CARD, "p-3.5", className)}>
      <span className="font-mono text-[8.5px] tracking-[0.14em] text-faint uppercase">Collected today</span>
      <p className="mt-1 text-[18px] font-medium tracking-[-0.02em] text-ink tabular-nums">
        <span className="mr-0.5 text-[0.65em] font-normal text-dim">₹</span>4,82,950
      </p>
      <svg viewBox="0 0 120 28" className="mt-1.5 h-7 w-full" fill="none">
        <path d="M0 24 L15 20 L30 22 L45 14 L60 16 L75 9 L90 11 L105 5 L120 3" stroke="var(--brand)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M0 24 L15 20 L30 22 L45 14 L60 16 L75 9 L90 11 L105 5 L120 3 V28 H0Z" fill="var(--brand)" opacity="0.08" />
      </svg>
      <p className="text-[9px] text-st-settled-fg">↑ 12% vs last Saturday</p>
    </div>
  );
}
