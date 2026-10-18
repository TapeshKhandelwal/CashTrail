"use client";

import { Check, ListFilter } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { FilterOption } from "@/hooks/use-data-table-state";
import { cn } from "@/lib/utils";

interface FacetedFilterProps {
  label: string;
  options: readonly FilterOption[];
  selected: string[];
  onChange: (selected: string[]) => void;
  /** Single choice (agent, branch) instead of multi-select (status). */
  single?: boolean;
  /** Optional counts per option value. */
  counts?: Record<string, number>;
}

/** Popover + command list filter; the trigger names what is chosen. */
export function FacetedFilter({ label, options, selected, onChange, single = false, counts }: FacetedFilterProps) {
  const chosen = new Set(selected);
  const toggle = (value: string) => {
    if (single) return onChange(chosen.has(value) ? [] : [value]);
    const next = new Set(chosen);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onChange([...next]);
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("gap-1.5 font-normal text-dim", chosen.size > 0 && "border-ink/25 text-ink")}
        >
          <ListFilter data-icon="inline-start" className="text-faint" />
          {label}
          {chosen.size > 0 && (
            <span className="ml-0.5 max-w-40 truncate font-medium text-ink">
              {chosen.size > 2
                ? `${chosen.size} selected`
                : options
                    .filter((option) => chosen.has(option.value))
                    .map((option) => option.label)
                    .join(", ")}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-60 p-0" align="start">
        <Command>
          {options.length > 7 && <CommandInput placeholder={label} />}
          <CommandList>
            <CommandEmpty>No matches.</CommandEmpty>
            <CommandGroup>
              {options.map((option) => {
                const isSelected = chosen.has(option.value);
                const Icon = option.icon;
                return (
                  <CommandItem key={option.value} value={option.label} onSelect={() => toggle(option.value)}>
                    <span
                      className={cn(
                        "flex size-4 items-center justify-center border",
                        single ? "rounded-full" : "rounded-sm",
                        isSelected ? "border-ink bg-ink text-paper" : "border-rule-strong",
                      )}
                    >
                      {isSelected && <Check className="size-3" />}
                    </span>
                    {Icon && <Icon className="text-faint" />}
                    <span>{option.label}</span>
                    {counts?.[option.value] !== undefined && (
                      <span className="ml-auto font-mono text-[11px] text-faint tabular-nums">{counts[option.value]}</span>
                    )}
                  </CommandItem>
                );
              })}
            </CommandGroup>
            {chosen.size > 0 && (
              <>
                <CommandSeparator />
                <CommandGroup>
                  <CommandItem onSelect={() => onChange([])} className="justify-center text-center text-dim">
                    Clear filter
                  </CommandItem>
                </CommandGroup>
              </>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
