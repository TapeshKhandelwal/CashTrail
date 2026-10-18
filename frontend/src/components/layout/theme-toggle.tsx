"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Match system", icon: Monitor },
] as const;

const subscribe = () => () => {};
/** next-themes only knows the stored theme after hydration. */
const useMounted = () => useSyncExternalStore(subscribe, () => true, () => false);

/** Three-way segmented control: Light / Dark / System. */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const mounted = useMounted();
  const current = mounted ? (theme ?? "system") : "system";

  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className={cn("flex h-8 shrink-0 items-center rounded-lg border border-rule bg-sunk p-0.5", className)}
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const active = current === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              "flex size-6.5 items-center justify-center rounded-md text-faint transition-[color,background-color,box-shadow] duration-150 outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-focus",
              active && "bg-raised text-ink shadow-lift",
            )}
          >
            <Icon className="size-3.5" aria-hidden />
          </button>
        );
      })}
    </div>
  );
}
