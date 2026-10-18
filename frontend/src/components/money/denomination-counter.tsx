"use client";

import { Minus, Plus } from "lucide-react";
import { useEffect, useRef, type PointerEvent } from "react";

import { AnimatedMoney } from "@/components/money/animated-money";
import { Money } from "@/components/money/money";
import { Button } from "@/components/ui/button";
import type { MoneyString } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { DenominationKey, Denominations } from "@/types/domain";

import {
  DEFAULT_DENOMINATIONS,
  denominationsTotal,
  fillDenominations,
  isCoin,
  lineTotal,
} from "./denominations";

const MAX_COUNT = 99_999;
const REPEAT_DELAY_MS = 400;
const REPEAT_EVERY_MS = 70;

interface DenominationCounterProps {
  value: Denominations;
  onChange: (next: Denominations) => void;
  /** Rows to show, largest first. Defaults to ₹500 down to ₹1 coins. */
  denominations?: DenominationKey[];
  /** Enables "Fill from declared" (largest-first split of this amount). */
  fillAmount?: MoneyString;
  /** Label for the fill button, e.g. "Fill from receipts". */
  fillLabel?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * Note-by-note cash count with an exact running total (paise BigInt). Steppers repeat on
 * long-press; ↑/↓ in a count field steps it; Tab moves between rows.
 *
 *   const [counts, setCounts] = useState<Denominations>({});
 *   <DenominationCounter value={counts} onChange={setCounts} fillAmount={submission.declared_amount} />
 *   denominationsTotal(counts) // "38500.00"
 */
export function DenominationCounter({
  value,
  onChange,
  denominations = DEFAULT_DENOMINATIONS,
  fillAmount,
  fillLabel = "Fill from declared",
  disabled = false,
  className,
}: DenominationCounterProps) {
  const total = denominationsTotal(value);
  const setCount = (key: DenominationKey, count: number) =>
    onChange({ ...value, [key]: Math.min(MAX_COUNT, Math.max(0, Math.trunc(count))) });

  return (
    <div className={cn("flex flex-col overflow-hidden rounded-xl border border-rule bg-raised", className)}>
      <div className="grid grid-cols-[1fr_auto] items-center border-b border-rule bg-sunk px-4 py-2 sm:grid-cols-[5.5rem_auto_1fr]">
        <span className="eyebrow">Note</span>
        <span className="eyebrow w-[10.25rem] text-center max-[22.5rem]:w-[9.75rem] sm:w-auto">Count</span>
        <span className="eyebrow text-right max-sm:hidden">Amount</span>
      </div>
      <ul className="divide-y divide-rule">
        {denominations.map((key) => (
          <DenominationRow
            key={key}
            denomination={key}
            count={value[key] ?? 0}
            onCount={(count) => setCount(key, count)}
            disabled={disabled}
          />
        ))}
      </ul>
      <div className="flex flex-wrap items-end gap-3 border-t border-rule bg-sunk/60 px-4 py-3.5">
        <div className="flex flex-col gap-1">
          <span className="eyebrow">Counted</span>
          <AnimatedMoney value={total} paise className="text-[22px] font-medium tracking-[-0.02em] text-ink" />
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => onChange({})} disabled={disabled || total === "0.00"}>
            Clear
          </Button>
          {fillAmount && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onChange(fillDenominations(fillAmount, denominations))}
              disabled={disabled}
            >
              {fillLabel}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function DenominationRow({
  denomination,
  count,
  onCount,
  disabled,
}: {
  denomination: DenominationKey;
  count: number;
  onCount: (count: number) => void;
  disabled: boolean;
}) {
  const label = `₹${denomination}`;
  const coin = isCoin(denomination);

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2.5 sm:grid-cols-[5.5rem_auto_1fr]">
      <span className="flex min-w-0 flex-col">
        <span className="font-mono text-[14px] text-ink tabular-nums">
          {label}
          <span className="ml-1.5 font-mono text-[10px] tracking-[0.12em] text-faint uppercase sm:hidden">{coin ? "Coin" : "Note"}</span>
        </span>
        <span className="font-mono text-[10px] tracking-[0.12em] text-faint uppercase max-sm:hidden">{coin ? "Coin" : "Note"}</span>
        {/* Phones: the line total sits under the note, so each row stays one stepper tall. */}
        <Money
          value={lineTotal(denomination, count)}
          className={cn("truncate text-[13px] sm:hidden", count === 0 ? "text-faint" : "text-dim")}
        />
      </span>
      <div className="flex items-center gap-1.5 justify-self-end sm:justify-self-center">
        <RepeatButton
          label={`One fewer ${label} ${coin ? "coin" : "note"}`}
          onStep={() => onCount(count - 1)}
          disabled={disabled || count === 0}
        >
          <Minus />
        </RepeatButton>
        <input
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete="off"
          aria-label={`Number of ${label} ${coin ? "coins" : "notes"}`}
          value={count === 0 ? "" : String(count)}
          placeholder="0"
          disabled={disabled}
          onChange={(event) => onCount(Number(event.target.value.replace(/\D/g, "") || 0))}
          onKeyDown={(event) => {
            if (event.key === "ArrowUp") {
              event.preventDefault();
              onCount(count + 1);
            } else if (event.key === "ArrowDown") {
              event.preventDefault();
              onCount(count - 1);
            }
          }}
          className="h-11 w-16 rounded-lg max-[22.5rem]:w-14 border border-rule-strong bg-raised text-center font-mono text-base tabular-nums outline-none placeholder:text-rule-strong focus-visible:border-ink focus-visible:ring-3 focus-visible:ring-focus disabled:opacity-50"
        />
        <RepeatButton
          label={`One more ${label} ${coin ? "coin" : "note"}`}
          onStep={() => onCount(count + 1)}
          disabled={disabled}
        >
          <Plus />
        </RepeatButton>
      </div>
      <Money
        value={lineTotal(denomination, count)}
        className={cn("justify-self-end text-[13.5px] max-sm:hidden", count === 0 ? "text-faint" : "text-ink")}
      />
    </li>
  );
}

/** 44px stepper that repeats while held; keyboard and assistive-tech clicks step once. */
function RepeatButton({
  label,
  onStep,
  disabled,
  children,
}: {
  label: string;
  onStep: () => void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  const latestStep = useRef(onStep);
  const timers = useRef<{ delay?: ReturnType<typeof setTimeout>; repeat?: ReturnType<typeof setInterval> }>({});

  useEffect(() => {
    latestStep.current = onStep;
  });

  const stop = () => {
    clearTimeout(timers.current.delay);
    clearInterval(timers.current.repeat);
  };
  useEffect(() => stop, []);

  const start = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    latestStep.current();
    timers.current.delay = setTimeout(() => {
      timers.current.repeat = setInterval(() => latestStep.current(), REPEAT_EVERY_MS);
    }, REPEAT_DELAY_MS);
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="size-11 rounded-lg"
      aria-label={label}
      disabled={disabled}
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      // Pointer presses are handled on pointerdown; clicks with detail 0 come from keys or screen readers.
      onClick={(event) => event.detail === 0 && onStep()}
    >
      {children}
    </Button>
  );
}
