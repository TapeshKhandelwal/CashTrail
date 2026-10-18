"use client";

import { Area, AreaChart } from "recharts";

/** 32px trend under a KPI value: 1.5px line, 6% fill, no axes or tooltip. */
export default function Sparkline({ data, color = "var(--brand)" }: { data: number[]; color?: string }) {
  const points = data.map((value, index) => ({ index, value }));
  return (
    <AreaChart data={points} style={{ width: "100%", height: 32 }} margin={{ top: 2, right: 0, bottom: 1, left: 0 }} responsive aria-hidden>
      <Area
        type="monotone"
        dataKey="value"
        stroke={color}
        strokeWidth={1.5}
        fill={color}
        fillOpacity={0.06}
        isAnimationActive={false}
        dot={false}
      />
    </AreaChart>
  );
}
