"use client";

import { useReducedMotion } from "motion/react";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

import {
  AXIS,
  BAR,
  chartAnimation,
  chartMoneyTick,
  chartNumber,
  ChartTooltip,
  CURSOR,
  GRID,
  SERIES,
} from "@/components/charts/chart-theme";
import { formatDayMonth } from "@/lib/dates";
import type { TrendPoint } from "@/types/domain";

/** One bar per day of what the agent collected, against the dues that fell due that day. */
export default function AgentTrendChart({ points, height }: { points: TrendPoint[]; height: number }) {
  const reduced = useReducedMotion();
  const data = points.map((point) => ({
    date: point.date,
    collected: chartNumber(point.collected),
    expected: chartNumber(point.expected),
  }));

  return (
    <BarChart barGap={2} data={data} style={{ width: "100%", height }} margin={{ top: 6, right: 4, bottom: 0, left: 0 }} responsive>
      <CartesianGrid {...GRID} />
      <XAxis dataKey="date" {...AXIS} tickFormatter={formatDayMonth} minTickGap={18} />
      <YAxis {...AXIS} width={52} tickFormatter={chartMoneyTick} />
      <Tooltip
        cursor={{ ...CURSOR, fill: "var(--sunk)" }}
        content={(props) => <ChartTooltip {...props} formatLabel={(label) => formatDayMonth(String(label))} formatValue={chartMoneyTick} />}
      />
      <Bar dataKey="expected" name="Due" {...BAR} maxBarSize={14} fill="var(--rule-strong)" {...chartAnimation(reduced)} />
      <Bar dataKey="collected" name="Collected" {...BAR} maxBarSize={14} fill={SERIES.pending} {...chartAnimation(reduced)} />
    </BarChart>
  );
}
