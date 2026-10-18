import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { Magnetic } from "@/components/motion/magnetic";
import { Button } from "@/components/ui/button";

const LINKS = [
  ["How it works", "#trace"],
  ["Reconciliation", "#count"],
  ["Controls", "#controls"],
  ["Roles", "#roles"],
] as const;

export function SiteNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-rule/70 bg-paper/80 pt-safe backdrop-blur-xl">
      <nav aria-label="Main" className="mx-auto flex h-15 max-w-6xl items-center justify-between px-5 sm:px-6">
        <Link href="/" className="group/logo" aria-label="CashTrail home">
          <Logo size="sm" />
        </Link>
        <div className="hidden items-center gap-7 text-[13.5px] text-dim md:flex">
          {LINKS.map(([label, href]) => (
            <a key={href} href={href} className="transition-colors hover:text-ink">
              {label}
            </a>
          ))}
        </div>
        <Magnetic>
          <Button asChild size="sm">
            <Link href="/login">Open the demo</Link>
          </Button>
        </Magnetic>
      </nav>
    </header>
  );
}
