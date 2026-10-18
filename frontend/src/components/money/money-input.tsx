"use client";

import { useLayoutEffect, useRef, useState, type ComponentProps } from "react";

import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from "@/components/ui/input-group";
import { formatAmount } from "@/lib/format";
import { MONEY_INPUT_PATTERN } from "@/lib/money";
import { cn } from "@/lib/utils";

/** Keeps digits and one dot with at most two decimals, as the person types. */
export function sanitizeMoneyInput(raw: string): string {
  const cleaned = raw.replace(/[^\d.]/g, "");
  const [whole, ...rest] = cleaned.split(".");
  if (rest.length === 0) return whole.replace(/^0+(?=\d)/, "");
  return `${whole.replace(/^0+(?=\d)/, "") || "0"}.${rest.join("").slice(0, 2)}`;
}

type MoneyInputProps = Omit<ComponentProps<"input">, "value" | "onChange" | "type" | "size"> & {
  /** Raw amount string ("12450.5"); empty string when blank. */
  value: string;
  onValueChange: (value: string) => void;
  /** `hero` is the large centred Collect-screen amount. */
  size?: "default" | "lg" | "hero";
  invalid?: boolean;
};

/**
 * Amount field: ₹ prefix, mono digits, decimal keyboard, en-IN grouping when not focused.
 * Validate with `parseMoneyInput(value)` from lib/money (null = invalid).
 */
export function MoneyInput({
  value,
  onValueChange,
  size = "default",
  invalid,
  className,
  onFocus,
  onBlur,
  ...props
}: MoneyInputProps) {
  const [focused, setFocused] = useState(false);
  const focusedInput = useRef<HTMLInputElement | null>(null);
  const display = !focused && MONEY_INPUT_PATTERN.test(value) ? formatAmount(value) : value;

  // Focus swaps the grouped text for the raw amount, which drops the browser's select-all.
  // Select again before the next keystroke so typing replaces a prefilled amount.
  useLayoutEffect(() => {
    const input = focusedInput.current;
    if (focused && input && document.activeElement === input) input.select();
  }, [focused]);

  return (
    <InputGroup
      data-size={size}
      className={cn(
        size === "lg" && "h-12",
        size === "hero" &&
          "h-auto justify-center border-0 bg-transparent shadow-none has-[[data-slot=input-group-control]:focus-visible]:ring-0",
        className,
      )}
    >
      <InputGroupAddon className={cn(size === "hero" && "pr-1")}>
        <InputGroupText
          className={cn(
            "font-normal text-faint",
            size === "lg" && "text-lg",
            size === "hero" && "font-sans text-[28px] font-normal text-dim",
          )}
        >
          ₹
        </InputGroupText>
      </InputGroupAddon>
      <InputGroupInput
        {...props}
        type="text"
        inputMode="decimal"
        enterKeyHint="done"
        autoComplete="off"
        spellCheck={false}
        aria-invalid={invalid || undefined}
        value={display}
        onChange={(event) => onValueChange(sanitizeMoneyInput(event.target.value))}
        onFocus={(event) => {
          focusedInput.current = event.currentTarget;
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        className={cn(
          "font-mono text-base tabular-nums md:text-base",
          size === "lg" && "text-lg md:text-lg",
          size === "hero" &&
            "h-auto w-[7ch] min-w-[3ch] flex-none py-1 font-sans text-[44px] leading-none md:text-[44px] font-medium tracking-[-0.025em] [field-sizing:content] placeholder:text-rule-strong supports-[field-sizing:content]:w-auto",
        )}
      />
    </InputGroup>
  );
}
