import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col bg-paper px-6 pt-safe pb-safe">
      <header className="mx-auto flex h-16 w-full max-w-5xl items-center">
        <Link href="/" aria-label="CashTrail home" className="rounded-md">
          <Logo size="sm" />
        </Link>
      </header>
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col justify-center pb-24">
        <p className="eyebrow">Error 404</p>
        <h1 className="mt-4 max-w-2xl font-display text-[clamp(2.4rem,6vw,4rem)] leading-[1.02] text-balance text-ink">
          This page doesn&apos;t exist.
        </h1>
        <p className="mt-4 max-w-md text-[16px] leading-relaxed text-dim">
          The address may be mistyped, or the record has moved. Nothing has been lost.
        </p>
        <div className="mt-8 flex flex-wrap gap-2">
          <Button asChild size="lg">
            <Link href="/app">Open CashTrail</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link href="/">Home</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
