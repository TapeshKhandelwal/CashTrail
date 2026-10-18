import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { Logo } from "@/components/brand/logo";
import { ProductCollage } from "@/components/marketing/product-collage";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to CashTrail with the account your branch admin gave you.",
};

export default function LoginPage() {
  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="flex min-h-dvh flex-col px-5 pt-safe pb-safe sm:px-10">
        <header className="flex h-16 items-center justify-between">
          <Link href="/" aria-label="CashTrail home" className="rounded-md">
            <Logo size="sm" />
          </Link>
          <Link href="/" className="-mr-2 rounded-md px-2 py-3 text-[13px] text-dim transition-colors hover:text-ink">
            Back to site
          </Link>
        </header>

        <main className="flex flex-1 items-start justify-center pt-8 pb-12 sm:items-center sm:pt-0 sm:pb-16">
          <div className="w-full max-w-[380px] animate-rise">
            <p className="eyebrow">Collections & reconciliation</p>
            <h1 className="mt-3 font-display text-[40px] leading-[1.02] tracking-[-0.025em] text-ink">Sign in</h1>
            <p className="mt-2.5 text-[14.5px] leading-relaxed text-dim">Use the account your branch admin gave you.</p>
            <div className="mt-8">
              <Suspense fallback={<LoginFormSkeleton />}>
                <LoginForm />
              </Suspense>
            </div>
          </div>
        </main>
      </div>

      <aside className="relative hidden flex-col justify-between gap-10 overflow-hidden border-l border-rule bg-paper p-10 lg:flex xl:p-14" aria-label="What CashTrail records">
        <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.14em] text-dim uppercase">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-brand/60 [animation-duration:2.4s]" />
            <span className="relative inline-flex size-1.5 rounded-full bg-brand" />
          </span>
          Demo · 45 days of activity across three branches
        </p>
        <ProductCollage className="aspect-[6/5] w-full max-w-[640px] self-center" />
        <div className="flex flex-col gap-4">
          <h2 className="font-display text-[clamp(2.4rem,3.6vw,3.25rem)] leading-[1] tracking-[-0.03em] text-ink">
            Five hand-offs.
            <br />
            <span className="text-dim">One ledger.</span>
          </h2>
          <p className="max-w-md text-[14.5px] leading-relaxed text-dim">
            Every rupee carries its receipt number from the doorstep to the bank statement. Nothing is edited once it settles.
          </p>
        </div>
      </aside>
    </div>
  );
}

function LoginFormSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-hidden>
      {[0, 1].map((index) => (
        <div key={index} className="flex flex-col gap-2">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <Skeleton className="h-10 w-full" />
    </div>
  );
}
