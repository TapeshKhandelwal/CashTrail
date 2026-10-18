import Link from "next/link";

import { Magnetic } from "@/components/motion/magnetic";
import { RevealLines } from "@/components/motion/reveal-lines";
import { Ticker } from "@/components/motion/ticker";
import { Button } from "@/components/ui/button";

import { LedgerField } from "./ledger-field";
import { ProductCollage } from "@/components/marketing/product-collage";

const EVENTS = [
  "RCT-BLR01-20261017-00412 · ₹2,450 collected · Ravi K.",
  "SUB-MUM01-20261017-003 · counted ₹48,500 of ₹50,000 · shortage raised",
  "DEP-DEL01-20261016-001 · ₹3,12,400 settled to HDFC ••4821",
  "UPI pay_G3qENEFvyXgcct · ₹8,710.62 captured",
  "DEP-BLR01-20261011-001 · past settlement SLA · flagged",
];

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden px-5 pt-32 pb-20 sm:px-6 sm:pt-40 sm:pb-28">
      <div className="parallax-slow pointer-events-none absolute -inset-y-[10%] inset-x-0">
        <LedgerField />
      </div>
      <div className="hero-depart relative mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] items-center gap-14 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)] lg:gap-10">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2.5 overflow-hidden">
            <span aria-hidden className="relative flex size-1.5">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-brand/60 [animation-duration:2.4s]" />
              <span className="relative inline-flex size-1.5 rounded-full bg-brand" />
            </span>
            <Ticker items={EVENTS} className="font-mono text-[11px] tracking-[0.12em] text-dim uppercase" />
          </div>

          <h1 className="mt-7 font-display text-[clamp(2.9rem,6.6vw,5.6rem)] leading-[0.95] tracking-[-0.035em] text-ink">
            <RevealLines lines={["Every rupee collected.", <span key="2" className="text-dim">Every rupee accounted for.</span>]} />
          </h1>

          <p className="reveal mt-8 max-w-xl text-[18px] leading-relaxed text-pretty text-dim">
            CashTrail follows a loan repayment from the customer&apos;s doorstep to the company&apos;s bank account: receipted by
            the agent, counted at the branch, matched at the bank, and locked once it settles.
          </p>

          <div className="reveal mt-10 flex flex-wrap items-center gap-3 max-sm:flex-col max-sm:items-stretch">
            <Magnetic className="max-sm:flex-col">
              <Button asChild size="lg" className="max-sm:h-12 max-sm:text-[15px]">
                <Link href="/login">Open the demo</Link>
              </Button>
            </Magnetic>
            <Button asChild size="lg" variant="outline" className="max-sm:h-12 max-sm:text-[15px]">
              <a href="#count">See a cash count</a>
            </Button>
          </div>

          <ul className="reveal mt-14 flex flex-wrap gap-x-6 gap-y-2.5 max-sm:flex-col max-sm:gap-y-2 font-mono text-[11px] tracking-[0.08em] text-faint uppercase">
            {["Receipt at the doorstep", "Counted at the branch", "Matched at the bank", "Locked once settled"].map((item, index) => (
              <li key={item} className="flex items-center gap-6">
                {index > 0 && <span aria-hidden className="text-rule-strong max-sm:hidden">/</span>}
                {item}
              </li>
            ))}
          </ul>
        </div>
        <ProductCollage className="reveal-lift aspect-[6/5] w-full max-sm:aspect-[3/4]" />
      </div>
    </section>
  );
}
