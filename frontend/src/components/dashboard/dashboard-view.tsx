"use client";

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import type { ReactNode } from "react";

import { ChartCard, type ChartTable } from "@/components/charts/chart-card";
import { ChartLegend, SERIES } from "@/components/charts/chart-theme";
import { ErrorState } from "@/components/feedback/error-state";
import { ChartSkeleton, KpiGridSkeleton } from "@/components/feedback/skeletons";
import { KpiGrid, KpiTile } from "@/components/kpi/kpi-tile";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { Money } from "@/components/money/money";
import { dashboardQueries } from "@/features/dashboard/api";
import { formatDayMonth, formatRange } from "@/lib/dates";
import { formatCount, formatPercent, countOf } from "@/lib/format";
import { isZero } from "@/lib/money";
import { collectionStatus } from "@/lib/status";
import type { DashboardParams, DashboardSummary } from "@/types/domain";

import { ActionStrip, type ActionDesk } from "./action-strip";
import { AttentionPanel, type AttentionLinks } from "./attention-panel";
import { DashboardFilterBar } from "./dashboard-filter-bar";
import { LifecycleFunnel } from "./lifecycle-funnel";
import { TeamTable } from "./team-table";
import { useDashboardFilters } from "./use-dashboard-filters";

const TrendChart = dynamic(() => import("./trend-chart"), { ssr: false, loading: () => <div className="h-full" /> });

const TREND_LEGEND = [
  { label: "Expected", color: SERIES.expected, dashed: true },
  { label: "Collected", color: SERIES.pending },
  { label: "Settled", color: SERIES.settled },
];

interface DashboardViewProps {
  eyebrow: ReactNode;
  title: string;
  description: string;
  /** Branch managers compare agents; global roles compare branches. */
  team: "agents" | "branches";
  desk: ActionDesk;
  links: AttentionLinks & { submissions?: string; atBranch?: string };
}

/**
 * The same instrument panel for every supervising role, scoped by the server: what was due,
 * what came in, where the cash is right now, how far it has travelled, and what is open.
 */
export function DashboardView({ eyebrow, title, description, team, desk, links }: DashboardViewProps) {
  const filters = useDashboardFilters();
  const { params } = filters;
  const summary = useQuery(dashboardQueries.summary(params));
  const trend = useQuery(dashboardQueries.trend(params));
  const lifecycle = useQuery(dashboardQueries.lifecycle(params));

  const period = summary.data ? formatRange({ from: summary.data.date_from, to: summary.data.date_to }) : null;

  return (
    <>
      <PageHeader
        eyebrow={eyebrow}
        title={title}
        description={description}
        actions={period && <span className="font-mono text-[11px] tracking-[0.12em] text-faint uppercase">{period}</span>}
      >
        <DashboardFilterBar filters={filters} />
      </PageHeader>

      <div className="flex flex-col gap-6">
        <ActionStrip desk={desk} branch={params.branch} />

        {params.status && <StatusNote status={params.status} />}

        {summary.isPending ? (
          <>
            <KpiGridSkeleton count={4} />
            <KpiGridSkeleton count={4} />
          </>
        ) : summary.isError ? (
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} bordered />
        ) : (
          <SummaryTiles summary={summary.data} links={links} />
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <ChartCard
            className="lg:col-span-2"
            eyebrow="Running total"
            title="Expected, collected and settled"
            summary="Cumulative expected dues against amounts collected (by receipt date) and settled (by bank date) across the selected period."
            loading={trend.isPending}
            error={trend.error}
            onRetry={() => void trend.refetch()}
            empty={trend.data?.every((point) => isZero(point.expected) && isZero(point.collected) && isZero(point.settled))}
            table={trend.data && trendTable(trend.data)}
            actions={<ChartLegend items={TREND_LEGEND} className="max-sm:hidden" />}
          >
            {trend.data && (
              <div className="flex h-full flex-col">
                <ChartLegend items={TREND_LEGEND} className="mb-3 sm:hidden" />
                <div className="min-h-0 flex-1">
                  <TrendChart points={trend.data} height="100%" />
                </div>
              </div>
            )}
          </ChartCard>

          <SectionCard
            eyebrow="Lifecycle"
            title="How far the money has travelled"
            description="Of receipts collected in this period, by the furthest stage reached."
          >
            {lifecycle.isPending ? (
              <ChartSkeleton height={220} className="border-0 p-0" />
            ) : lifecycle.isError ? (
              <ErrorState error={lifecycle.error} onRetry={() => void lifecycle.refetch()} compact />
            ) : (
              <LifecycleFunnel lifecycle={lifecycle.data} />
            )}
          </SectionCard>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <TeamTable scope={team} params={params} />
          </div>
          <AttentionPanel branch={params.branch} links={links} />
        </div>
      </div>
    </>
  );
}

/** Says which figures a receipt status narrows, so a cut total is never read as the whole. */
function StatusNote({ status }: { status: NonNullable<DashboardParams["status"]> }) {
  return (
    <p className="border-l-2 border-rule pl-3 text-[13px] text-dim">
      Showing only receipts now marked <span className="text-ink">{collectionStatus(status).label}</span>. Expected,
      Outstanding, Received in period, deposit accuracy and open discrepancies are not narrowed by status.
    </p>
  );
}

function SummaryTiles({ summary, links }: { summary: DashboardSummary; links: DashboardViewProps["links"] }) {
  const oldBucket = summary.cash_ageing.find((row) => row.bucket === "over_2_days");

  return (
    <>
      <KpiGrid columns={4}>
        <KpiTile
          label="Expected"
          amount={summary.expected.amount}
          context={`${countOf(summary.expected.count, "instalment")} due`}
          info="Instalment amounts falling due in the period."
        />
        <KpiTile
          label="Collected"
          amount={summary.collected.amount}
          info="Receipts collected during the period, excluding voided ones."
          context={
            <span>
              <Money value={summary.collected.cash.amount} whole compact /> cash ·{" "}
              <Money value={summary.collected.upi.amount} whole compact /> UPI
            </span>
          }
          delta={
            summary.collection_efficiency
              ? {
                  value: formatPercent(summary.collection_efficiency, 0),
                  direction: Number(summary.collection_efficiency) >= 100 ? "up" : "down",
                  good: Number(summary.collection_efficiency) >= 90,
                  label: "of expected",
                }
              : undefined
          }
        />
        <KpiTile
          label="Settled in period"
          tone="settled"
          amount={summary.settled.amount}
          context={
            summary.avg_settlement_lag_days
              ? `${countOf(summary.settled.count, "receipt")} · ${Number(summary.avg_settlement_lag_days).toFixed(1)}d average lag`
              : `${countOf(summary.settled.count, "receipt")}`
          }
          info="Receipts credited to the company account during the period, by bank date, whenever they were collected. Confirmed against the bank statement or gateway settlement."
        />
        <KpiTile
          label="Outstanding"
          amount={summary.outstanding.amount}
          context={
            isZero(summary.overdue.amount) ? (
              "Nothing overdue"
            ) : (
              <span>
                <Money value={summary.overdue.amount} whole tone="short" /> overdue
              </span>
            )
          }
          info="Unpaid balance on active loans, as of now."
        />
      </KpiGrid>

      <section aria-labelledby="where-cash" className="flex flex-col gap-3">
        <h2 id="where-cash" className="eyebrow">
          Where the cash is right now
        </h2>
        <KpiGrid columns={4}>
          <KpiTile
            label="With agents"
            tone="collected"
            amount={summary.cash_with_agents.amount}
            context={
              oldBucket && !isZero(oldBucket.amount) ? (
                <span className="text-st-delayed-fg">
                  <Money value={oldBucket.amount} whole /> held over 2 days
                </span>
              ) : (
                `${countOf(summary.cash_with_agents.count, "receipt")} not yet handed over`
              )
            }
          />
          <KpiTile
            label="Awaiting count"
            tone="submitted"
            amount={summary.pending_verification.amount}
            context={`${countOf(summary.pending_verification.count, "receipt")} handed over`}
            href={links.submissions}
          />
          <KpiTile
            label="At branch"
            tone="received"
            amount={summary.at_branch.amount}
            context="Counted, not yet deposited"
            href={links.atBranch}
          />
          <KpiTile
            label="In the bank"
            tone="deposited"
            amount={summary.pending_deposits.amount}
            context={
              summary.delayed_settlements.count > 0 ? (
                <span className="text-st-delayed-fg">
                  {formatCount(summary.delayed_settlements.count)} past settlement SLA
                </span>
              ) : (
                `${countOf(summary.pending_deposits.count, "deposit")} awaiting settlement`
              )
            }
            href={links.deposits}
          />
        </KpiGrid>
      </section>

      <ControlStrip summary={summary} />
    </>
  );
}

/** Ratios that tell a supervisor whether the process is healthy, in one quiet line. */
function ControlStrip({ summary }: { summary: DashboardSummary }) {
  const items: [string, ReactNode][] = [
    ["Open discrepancies", <><Money key="a" value={summary.discrepancies.open.amount} whole tone={isZero(summary.discrepancies.open.amount) ? "none" : "short"} /> · {formatCount(summary.discrepancies.open.count)}</>],
    ["Deposit accuracy", formatPercent(summary.deposit_accuracy, 0)],
    ["Voided receipts", formatCount(summary.voided.count)],
    ["Received in period", <Money key="b" value={summary.branch_received.amount} whole />],
  ];
  return (
    <dl className="grid-ruled grid-cols-2 lg:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3 sm:px-5">
          <dt className="eyebrow">{label}</dt>
          <dd className="text-[15px] whitespace-nowrap text-ink tabular-nums sm:text-[13.5px]">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function trendTable(points: { date: string; expected: string; collected: string; settled: string }[]): ChartTable {
  return {
    columns: [
      { key: "date", label: "Date" },
      { key: "expected", label: "Expected", align: "end" },
      { key: "collected", label: "Collected", align: "end" },
      { key: "settled", label: "Settled", align: "end" },
    ],
    rows: points.map((point) => ({
      date: formatDayMonth(point.date),
      expected: <Money value={point.expected} whole />,
      collected: <Money value={point.collected} whole />,
      settled: <Money value={point.settled} whole />,
    })),
  };
}

