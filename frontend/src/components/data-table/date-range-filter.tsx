"use client";

import { CalendarRange } from "lucide-react";
import type { DateRange as DayPickerRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  DATE_RANGE_PRESETS,
  formatRange,
  fromPickerDate,
  presetRange,
  toPickerDate,
  todayIST,
  type DateRange,
} from "@/lib/dates";
import { cn } from "@/lib/utils";

interface DateRangeFilterProps {
  label?: string;
  value: Partial<DateRange>;
  onChange: (range: { from: string | null; to: string | null }) => void;
  /** Disallow future dates (default). */
  maxToday?: boolean;
  className?: string;
}

/** Presets (Today, Yesterday, Last 7 days, This month…) plus a two-month range calendar. */
export function DateRangeFilter({ label = "Date", value, onChange, maxToday = true, className }: DateRangeFilterProps) {
  const isMobile = useIsMobile();
  const today = todayIST();
  const selected: DayPickerRange | undefined = value.from
    ? { from: toPickerDate(value.from), to: value.to ? toPickerDate(value.to) : undefined }
    : undefined;
  const active = Boolean(value.from);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("gap-1.5 font-normal text-dim", active && "border-ink/25 text-ink", className)}
        >
          <CalendarRange data-icon="inline-start" className="text-faint" />
          {active ? (
            <span className="font-medium tabular-nums">{formatRange({ from: value.from!, to: value.to ?? value.from! })}</span>
          ) : (
            label
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-auto p-0">
        <div className="flex flex-col sm:flex-row">
          {/* Phones: the presets scroll in a row as wide as the calendar, never wider. */}
          <ul
            className="flex gap-1 overflow-x-auto border-b border-rule p-2 max-sm:w-0 max-sm:min-w-full max-sm:scrollbar-none sm:flex-col sm:border-r sm:border-b-0"
            aria-label="Quick ranges"
          >
            {DATE_RANGE_PRESETS.map((preset) => {
              const range = presetRange(preset.id, today);
              const isCurrent = value.from === range.from && value.to === range.to;
              return (
                <li key={preset.id}>
                  <Button
                    variant={isCurrent ? "secondary" : "ghost"}
                    size="sm"
                    className="w-full justify-start whitespace-nowrap"
                    onClick={() => onChange(range)}
                  >
                    {preset.label}
                  </Button>
                </li>
              );
            })}
            {active && (
              <li>
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full justify-start text-faint"
                  onClick={() => onChange({ from: null, to: null })}
                >
                  Clear
                </Button>
              </li>
            )}
          </ul>
          <Calendar
            mode="range"
            numberOfMonths={isMobile ? 1 : 2}
            defaultMonth={selected?.from}
            selected={selected}
            disabled={maxToday ? { after: toPickerDate(today) } : undefined}
            onSelect={(range) =>
              onChange({
                from: range?.from ? fromPickerDate(range.from) : null,
                to: range?.to ? fromPickerDate(range.to) : range?.from ? fromPickerDate(range.from) : null,
              })
            }
            className="[--cell-size:--spacing(9)]"
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
