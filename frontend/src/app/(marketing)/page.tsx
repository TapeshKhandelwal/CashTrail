import { CasesBento } from "@/components/landing/cases-bento";
import { CashFlow } from "@/components/landing/cash-flow";
import { CountDemo } from "@/components/landing/count-demo";
import { Hero } from "@/components/landing/hero";
import { RolesSection } from "@/components/landing/roles-section";
import { SectionHeading } from "@/components/landing/section-heading";
import { SiteNav } from "@/components/landing/site-nav";
import { ClosingCta, SiteFooter } from "@/components/landing/site-footer";
import { TraceDemo } from "@/components/landing/trace-demo";
import { AuditExcerpt, UpiPanel } from "@/components/landing/upi-and-controls";
import { RevealObserver } from "@/components/motion/reveal-observer";

const STATS: [string, string][] = [
  ["5", "hand-offs tracked per rupee"],
  ["0", "edits after settlement"],
  ["₹0.01", "reconciled to the paisa"],
  ["2 days", "settlement SLA, then flagged"],
];

export default function LandingPage() {
  return (
    <div className="bg-paper text-ink">
      <SiteNav />
      <main>
        <Hero />

        <div className="hairline h-px" />

        <section className="px-5 py-16 sm:px-6">
          <dl className="stagger mx-auto grid max-w-6xl grid-cols-2 gap-y-10 lg:grid-cols-4">
            {STATS.map(([value, label]) => (
              <div key={label} className="flex flex-col gap-1.5 border-rule px-2 sm:px-6 lg:not-first:border-l">
                <dt className="order-2 text-[13.5px] text-dim">{label}</dt>
                <dd className="order-1 font-display text-[clamp(2.2rem,4vw,3rem)] leading-none tracking-[-0.03em] text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section id="flow" className="border-y border-rule bg-sunk px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              eyebrow="The trail"
              title="Five hands touch the money. Each one leaves a record."
              lead="Every hand-off is a state change the system enforces, with who did it, when, and the reference that proves it."
            />
            <div className="mt-14">
              <CashFlow />
            </div>
          </div>
        </section>

        <section id="trace" className="px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              center
              eyebrow="Trace a rupee"
              title="One receipt, from the doorstep to the statement"
              lead="Step a real-looking ₹2,450 repayment through every hand-off, then try to change it after it settles."
            />
            <div className="reveal-mask mt-12">
              <TraceDemo />
            </div>
          </div>
        </section>

        <section id="count" className="border-y border-rule bg-sunk px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              center
              eyebrow="The count"
              title="₹50,000 receipted. ₹48,500 in the bag."
              lead="The branch counts every hand-over itself. Change the notes and watch the difference, the action and the ledger entry follow."
            />
            <div className="reveal-mask mt-12">
              <CountDemo />
            </div>
          </div>
        </section>

        <section id="cases" className="px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              eyebrow="When things go wrong"
              title="Rules, not reminders"
              lead="Each of these is enforced by the service layer and, for anything reconciled, by the database itself. A wrong number can't sneak through on a busy evening."
            />
            <CasesBento />
          </div>
        </section>

        <section id="roles" className="border-y border-rule bg-sunk px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              eyebrow="Four desks"
              title="Each role sees exactly its part of the ledger"
              lead="Agents see their own route; managers see their branch; finance and admins see everything. The server enforces it, not the menu."
            />
            <RolesSection />
          </div>
        </section>

        <section id="upi" className="px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <UpiPanel />
          </div>
        </section>

        <section id="controls" className="border-t border-rule bg-sunk px-5 py-24 sm:px-6 sm:py-32">
          <div className="mx-auto max-w-6xl">
            <SectionHeading
              eyebrow="Controls"
              title="An audit trail nobody can rewrite"
              lead="Who did what, when, from where, with the values before and after. The table is append-only at the database, so history stays history."
            />
            <div className="mt-12">
              <AuditExcerpt />
            </div>
          </div>
        </section>

        <ClosingCta />
      </main>
      <SiteFooter />
      {/* Rendered with the page, not the layout, so classes are only added once this tree has hydrated. */}
      <RevealObserver />
    </div>
  );
}
