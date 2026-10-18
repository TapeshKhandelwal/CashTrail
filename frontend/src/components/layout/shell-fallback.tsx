import { LogoMark } from "@/components/brand/logo-mark";

/** While the session resolves: the shell's outline on paper, with the mark where the logo sits. */
export function ShellFallback() {
  return (
    <div role="status" aria-label="Opening CashTrail" className="flex min-h-dvh bg-paper">
      <div className="hidden w-[248px] shrink-0 border-r border-rule md:block">
        <div className="flex h-14 items-center border-b border-rule px-4">
          <LogoMark className="size-[18px]" />
        </div>
      </div>
      <div className="flex flex-1 flex-col">
        <div className="h-14 border-b border-rule" />
        <div className="relative h-0.5 overflow-hidden">
          <div className="h-full w-full origin-left animate-[top-progress_1.2s_var(--ease-out-quint)_infinite] bg-brand" />
        </div>
      </div>
    </div>
  );
}
