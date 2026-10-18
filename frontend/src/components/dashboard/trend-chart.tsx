"use client";

import { useReducedMotion } from "motion/react";
import { Area, CartesianGrid, ComposedChart, Line, Tooltip, XAxis, YAxis } from "recharts";

import {
  AREA,
  AXIS,
  chartAnimation,
  chartMoneyTick,
  chartNumber,
  ChartTooltip,
  CURSOR,
  GRID,
  LINE,
  SERIES,
} from "@/components/charts/chart-theme";
import { formatDayMonth } from "@/lib/dates";
import { addMoney } from "@/lib/money";
import type { TrendPoint } from "@/types/domain";

/**
 * Running totals across the period: expected (dashed ink), collected (amber area: cash in the
 * field) and settled (green). Daily figures arrive in spikes; the gap between the curves is
 * the story.
 */
export default function TrendChart({ points, height }: { points: TrendPoint[]; height: number | string }) {
  const reduced = useReducedMotion();
  const data = cumulative(points).map((point) => ({
    date: point.date,
    expected: chartNumber(point.expected),
    collected: chartNumber(point.collected),
    settled: chartNumber(point.settled),
  }));

  return (
    <ComposedChart data={data} style={{ width: "100%", height }} margin={{ top: 6, right: 4, bottom: 0, left: 0 }} responsive>
      <CartesianGrid {...GRID} />
      <XAxis dataKey="date" {...AXIS} tickFormatter={formatDayMonth} minTickGap={28} />
      <YAxis {...AXIS} width={56} tickFormatter={chartMoneyTick} />
      <Tooltip
        cursor={CURSOR}
        content={(props) => (
          <ChartTooltip {...props} formatLabel={(label) => formatDayMonth(String(label))} formatValue={chartMoneyTick} />
        )}
      />
      <Area dataKey="collected" name="Collected" {...AREA} type="stepAfter" stroke={SERIES.pending} fill={SERIES.pending} {...chartAnimation(reduced)} />
      <Line dataKey="settled" name="Settled" {...LINE} type="stepAfter" stroke={SERIES.settled} {...chartAnimation(reduced)} />
      <Line dataKey="expected" name="Expected" {...LINE} type="stepAfter" stroke={SERIES.expected} strokeDasharray="4 4" {...chartAnimation(reduced)} />
    </ComposedChart>
  );
}

export function cumulative(points: TrendPoint[]): TrendPoint[] {
  let expected = "0.00";
  let collected = "0.00";
  let settled = "0.00";
  return points.map((point) => {
    expected = addMoney(expected, point.expected);
    collected = addMoney(collected, point.collected);
    settled = addMoney(settled, point.settled);
    return { date: point.date, expected, collected, settled };
  });
}
