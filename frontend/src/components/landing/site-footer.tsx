import Link from "next/link";

import { LogoLockup } from "@/components/brand/logo";
import { Magnetic } from "@/components/motion/magnetic";
import { Button } from "@/components/ui/button";

export function ClosingCta() {
  return (
    <section className="relative overflow-hidden px-5 py-28 sm:px-6 sm:py-36">
      <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_120%,color-mix(in_oklab,var(--brand)_16%,transparent),transparent_62%)]" />
      <div className="relative mx-auto max-w-3xl text-center">
        <h2 className="reveal-blur font-display text-[clamp(2.4rem,5.6vw,4.2rem)] leading-[1] tracking-[-0.03em] text-balance text-ink">
          Follow one rupee, start to finish.
        </h2>
        <p className="reveal mx-auto mt-5 max-w-lg text-[17.5px] leading-relaxed text-dim">
          The demo is seeded with six weeks of collections, counts, deposits and settlements across three branches. Sign in as
          any role.
        </p>
        <div className="reveal mt-9 flex flex-wrap justify-center gap-3 max-sm:flex-col max-sm:items-stretch">
          <Magnetic className="max-sm:flex-col">
            <Button asChild size="lg" className="max-sm:h-12 max-sm:text-[15px]">
              <Link href="/login">Open the demo</Link>
            </Button>
          </Magnetic>
          <Button asChild size="lg" variant="outline" className="max-sm:h-12 max-sm:text-[15px]">
            <a href="#trace">Trace a rupee</a>
          </Button>
        </div>
        <p className="reveal mt-6 font-mono text-[11px] tracking-[0.08em] text-faint">Demo password Demo@12345</p>
      </div>
    </section>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-rule px-5 pt-14 pb-safe-offset-10 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex max-w-xs flex-col gap-4">
          <LogoLockup size="sm" />
          <p className="text-[13px] leading-relaxed text-dim">Cash collection and reconciliation for lenders whose customers repay at the door.</p>
        </div>
        <div className="grid grid-cols-2 gap-x-16 gap-y-2 text-[13.5px] max-sm:gap-x-6 max-sm:gap-y-0 max-sm:text-[15px] max-sm:[&>a]:py-2.5">
          <p className="eyebrow col-span-2 mb-1">Product</p>
          <a href="#trace" className="text-dim hover:text-ink">How it works</a>
          <a href="#count" className="text-dim hover:text-ink">Reconciliation</a>
          <a href="#controls" className="text-dim hover:text-ink">Controls</a>
          <a href="#roles" className="text-dim hover:text-ink">Roles</a>
          <Link href="/login" className="text-dim hover:text-ink">Sign in</Link>
        </div>
      </div>
      <div className="mx-auto mt-12 flex max-w-6xl flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-t border-rule pt-6 font-mono text-[11px] text-faint">
        <span>Built with Django, PostgreSQL and Next.js</span>
        <span>Amounts in INR · times in IST</span>
      </div>
    </footer>
  );
}
