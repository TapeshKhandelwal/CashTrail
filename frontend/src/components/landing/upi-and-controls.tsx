import { Check } from "lucide-react";

/** UPI: the same receipt, ledger and settlement matching as cash, net of the gateway's cut. */
export function UpiPanel() {
  const lines: [string, string, string?][] = [
    ["Gross captured · 6 payments", "₹45,623.43"],
    ["Gateway fee", "− ₹912.47", "text-dim"],
    ["GST on fee", "− ₹164.24", "text-dim"],
    ["Expected credit", "₹44,546.72", "text-ink font-medium"],
    ["Credited · UTR KKBKR2610139…", "₹44,546.72", "text-st-settled-fg font-medium"],
  ];
  return (
    <div className="reveal-mask grid overflow-hidden rounded-2xl border border-rule bg-raised shadow-float md:grid-cols-2">
      <div className="flex flex-col justify-between gap-8 border-rule p-6 max-md:border-b md:border-r sm:p-9">
        <div className="flex flex-col gap-3">
          <p className="font-mono text-[11px] tracking-[0.16em] text-st-upi-fg uppercase">UPI, same ledger</p>
          <h3 className="font-display text-[clamp(1.625rem,7vw,1.75rem)] leading-[1.08] max-sm:text-balance tracking-[-0.02em] text-ink">The customer pays from their phone. The receipt is the same.</h3>
          <p className="text-[15px] leading-relaxed text-dim">
            A UPI payment is receipted only when the gateway confirms it, verified by signature, and it never enters an
            agent&apos;s cash in hand. Finance settles it against the gateway&apos;s batch just as it settles a branch deposit.
          </p>
        </div>
        <ul className="flex flex-col gap-2 text-[13.5px] text-dim">
          {["Signature-verified checkout and webhooks", "Webhook replays are ignored, never double-counted", "Fees and tax reconciled to the paisa"].map((item) => (
            <li key={item} className="flex items-start gap-2.5">
              <Check className="mt-[3px] size-3.5 shrink-0 text-st-settled-fg" strokeWidth={2.25} />
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div className="flex flex-col justify-center gap-4 bg-sunk/60 p-6 sm:p-9">
        <p className="font-mono text-[10.5px] tracking-[0.14em] text-faint uppercase">DEP-GATEWAY-20261013-001</p>
        <ul className="divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
          {lines.map(([label, value, tone]) => (
            <li key={label} className="flex items-center justify-between gap-4 px-4 py-3 text-[13.5px]">
              <span className="min-w-0 text-dim">{label}</span>
              <span className={`shrink-0 tabular-nums ${tone ?? "text-ink"}`}>{value}</span>
            </li>
          ))}
        </ul>
        <p className="text-[12.5px] text-dim">Any gap between expected and credited becomes a gateway mismatch for finance to resolve.</p>
      </div>
    </div>
  );
}

const AUDIT: [string, string, string, string][] = [
  ["10:30:12", "Submission approved", "Kavitha Rao", "received ₹48,500.00 → discrepancy ₹1,500.00"],
  ["14:02:47", "Deposit created", "Kavitha Rao", "HDFC ••4821 · ref HDFC261017218378"],
  ["15:31:05", "Deposit settled", "Priya Raghavan", "₹3,12,400.00 · STMT-20261017-9812"],
  ["15:44:19", "Update refused", "—", "collections.amount on a settled receipt"],
];

/** An excerpt of the audit log: who, what, when, and the values that changed. */
export function AuditExcerpt() {
  return (
    <div className="reveal-mask overflow-hidden rounded-2xl border border-rule bg-raised shadow-float">
      <div className="flex items-center gap-2 border-b border-rule bg-sunk px-4 py-2.5">
        <span className="size-2 rounded-full bg-rule-strong" />
        <span className="size-2 rounded-full bg-rule-strong" />
        <span className="size-2 rounded-full bg-rule-strong" />
        <span className="ml-2 font-mono text-[10.5px] tracking-[0.14em] text-faint uppercase">audit log · append-only</span>
      </div>
      <ol className="divide-y divide-rule sm:hidden">
        {AUDIT.map(([time, action, actor, detail]) => (
          <li key={time} className="flex flex-col gap-1 px-4 py-3.5">
            <span className="flex items-baseline justify-between gap-3">
              <span className={`text-[14px] ${action === "Update refused" ? "text-st-rejected-fg" : "text-ink"}`}>{action}</span>
              <span className="shrink-0 font-mono text-[11.5px] text-faint tabular-nums">{time}</span>
            </span>
            {actor !== "—" && <span className="text-[12.5px] text-dim">{actor}</span>}
            <span className="font-mono text-[11px] leading-relaxed break-words text-dim">{detail}</span>
          </li>
        ))}
      </ol>
      <div className="overflow-x-auto max-sm:hidden">
        <table className="w-full min-w-[640px] text-[13px]">
          <thead>
            <tr className="border-b border-rule">
              {["Time", "Action", "By", "Recorded"].map((label) => (
                <th key={label} className="h-9 px-4 text-left font-mono text-[10.5px] font-normal tracking-[0.12em] text-faint uppercase">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {AUDIT.map(([time, action, actor, detail]) => (
              <tr key={time}>
                <td className="h-11 px-4 font-mono text-[12px] text-faint">{time}</td>
                <td className={`px-4 ${action === "Update refused" ? "text-st-rejected-fg" : "text-ink"}`}>{action}</td>
                <td className="px-4 text-dim">{actor}</td>
                <td className="px-4 font-mono text-[11.5px] text-dim">{detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
