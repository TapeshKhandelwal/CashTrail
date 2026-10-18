"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowRightLeft, Plus } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { parseAsStringLiteral, useQueryState } from "nuqs";

import { ChartCard } from "@/components/charts/chart-card";
import { ChartLegend, SERIES } from "@/components/charts/chart-theme";
import { LifecycleFunnel } from "@/components/dashboard/lifecycle-funnel";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { CardListSkeleton, ChartSkeleton, KpiGridSkeleton } from "@/components/feedback/skeletons";
import { KpiGrid, KpiTile } from "@/components/kpi/kpi-tile";
import { PageHeader } from "@/components/layout/page-header";
import { SectionCard } from "@/components/layout/section-card";
import { Segmented } from "@/components/layout/segmented";
import { Money } from "@/components/money/money";
import { useSession } from "@/components/providers/session-provider";
import { ModeChip } from "@/components/status/mode-chip";
import { StatusChip } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { collectionQueries } from "@/features/collections/api";
import { customerQueries } from "@/features/customers/api";
import { dashboardQueries } from "@/features/dashboard/api";
import { addDays, formatDayMonth, formatLongDay, formatRelative, formatTime, greeting, todayIST } from "@/lib/dates";
import { countOf, formatPercent } from "@/lib/format";
import { isZero, moneyRatio } from "@/lib/money";
import type { DailySummary, DashboardSummary } from "@/types/domain";

import { CustomerRow } from "./customer-row";

const AgentTrendChart = dynamic(() => import("./agent-trend-chart"), { ssr: false, loading: () => <div className="h-[220px]" /> });

const VIEWS = ["overdue", "today", "all"] as const;
type View = (typeof VIEWS)[number];
const TREND_DAYS = 14;

export function AgentToday() {
  const user = useSession();
  const today = todayIST();
  const daily = useQuery(collectionQueries.dailySummary());
  const month = useQuery(dashboardQueries.summary());
  const overdue = useQuery(customerQueries.agentRoute({ due: "overdue", page_size: 1 }));

  return (
    <>
      <PageHeader
        eyebrow={formatLongDay(new Date())}
        title={`${greeting()}, ${user.first_name || user.full_name}.`}
        description="Your route, the cash you are carrying, and how this month is going."
        actions={
          <>
            <Button asChild variant="outline" className="max-md:hidden">
              <Link href="/app/agent/handover">
                <ArrowRightLeft data-icon="inline-start" />
                Hand over cash
              </Link>
            </Button>
            <Button asChild className="max-md:hidden">
              <Link href="/app/agent/collect">
                <Plus data-icon="inline-start" />
                Collect
              </Link>
            </Button>
          </>
        }
      />

      <div className="flex flex-col gap-6">
        {daily.isPending || month.isPending ? (
          <KpiGridSkeleton count={4} />
        ) : daily.isError ? (
          <ErrorState error={daily.error} onRetry={() => void daily.refetch()} bordered compact />
        ) : month.isError ? (
          <ErrorState error={month.error} onRetry={() => void month.refetch()} bordered compact />
        ) : (
          <>
            <Kpis daily={daily.data} month={month.data} overdueCustomers={overdue.data?.count ?? 0} />
            {!isZero(daily.data.unsubmitted_cash) && <HandOverPrompt daily={daily.data} />}
          </>
        )}

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <div className="flex min-w-0 flex-col gap-6">
            <Trend from={addDays(today, -(TREND_DAYS - 1))} to={today} />
            <Route />
          </div>
          <div className="flex min-w-0 flex-col gap-6">
            <Journey />
            {month.data && <ModeSplit summary={month.data} />}
          </div>
          <div className="lg:col-span-2">
            <RecentReceipts />
          </div>
        </div>
      </div>
    </>
  );
}

function Kpis({ daily, month, overdueCustomers }: { daily: DailySummary; month: DashboardSummary; overdueCustomers: number }) {
  const oldest = month.cash_ageing.find((bucket) => bucket.bucket === "over_2_days" && !isZero(bucket.amount))
    ? "some held over 2 days"
    : month.cash_ageing.find((bucket) => bucket.bucket === "1_to_2_days" && !isZero(bucket.amount))
      ? "held since yesterday"
      : "collected today";
  const efficiency = month.collection_efficiency;

  return (
    <KpiGrid columns={4}>
      <KpiTile
        label="Collected today"
        amount={daily.total_amount}
        context={`${countOf(daily.count, "receipt")}${daily.upi_count ? ` · ${daily.upi_count} by UPI` : ""}`}
        href="/app/agent/collections"
      />
      <KpiTile
        label="Cash in hand"
        tone="collected"
        amount={daily.unsubmitted_cash}
        context={isZero(daily.unsubmitted_cash) ? "Nothing to hand over" : `${countOf(daily.unsubmitted_count, "receipt")} · ${oldest}`}
        href="/app/agent/handover"
      />
      <KpiTile
        label="This month"
        tone="settled"
        amount={month.collected.amount}
        context={<span>of <Money value={month.expected.amount} whole /> due</span>}
        delta={
          efficiency
            ? {
                value: formatPercent(efficiency, 0),
                direction: Number(efficiency) >= 100 ? "up" : "down",
                good: Number(efficiency) >= 90,
                label: "collected",
              }
            : undefined
        }
      />
      <KpiTile
        label="Overdue"
        tone="short"
        amount={month.overdue.amount}
        context={overdueCustomers ? `${countOf(overdueCustomers, "customer")} to visit first` : "Nobody is overdue"}
      />
    </KpiGrid>
  );
}

function HandOverPrompt({ daily }: { daily: DailySummary }) {
  return (
    <Link
      href="/app/agent/handover"
      className="group flex items-center justify-between gap-4 rounded-xl border border-st-collected/30 bg-st-collected/6 px-5 py-4 transition-colors hover:bg-st-collected/10"
    >
      <span className="flex flex-col gap-0.5">
        <span className="text-[14px] text-ink">
          Hand over <Money value={daily.unsubmitted_cash} /> at the branch
        </span>
        <span className="text-[12.5px] text-dim">
          {countOf(daily.unsubmitted_count, "receipt")} waiting. Cash is your responsibility until the branch counts it.
        </span>
      </span>
      <ArrowRight aria-hidden className="size-4 shrink-0 text-st-collected-fg transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

function Trend({ from, to }: { from: string; to: string }) {
  const trend = useQuery(dashboardQueries.trend({ date_from: from, date_to: to }));
  return (
    <ChartCard
      eyebrow={`Last ${TREND_DAYS} days`}
      title="What you collected, day by day"
      summary="Daily amounts collected by you against instalments falling due on your route."
      height={220}
      loading={trend.isPending}
      error={trend.error}
      onRetry={() => void trend.refetch()}
      empty={trend.data?.every((point) => isZero(point.collected) && isZero(point.expected))}
      emptyTitle="No collections in the last two weeks."
      actions={
        <ChartLegend
          items={[
            { label: "Collected", color: SERIES.pending },
            { label: "Due", color: "var(--rule-strong)" },
          ]}
        />
      }
      table={
        trend.data && {
          columns: [
            { key: "date", label: "Date" },
            { key: "due", label: "Due", align: "end" },
            { key: "collected", label: "Collected", align: "end" },
          ],
          rows: trend.data.map((point) => ({
            date: formatDayMonth(point.date),
            due: <Money value={point.expected} />,
            collected: <Money value={point.collected} />,
          })),
        }
      }
    >
      {trend.data && <AgentTrendChart points={trend.data} height={220} />}
    </ChartCard>
  );
}

function Route() {
  const [view, setView] = useQueryState("view", parseAsStringLiteral(VIEWS).withDefault("overdue"));
  const overdue = useQuery(customerQueries.agentRoute({ due: "overdue", page_size: 1 }));
  const dueToday = useQuery(customerQueries.agentRoute({ due: "today", page_size: 1 }));
  const route = useQuery(customerQueries.agentRoute({ due: view === "all" ? undefined : view, page_size: 50 }));

  return (
    <section aria-labelledby="route-title" className="flex flex-col gap-3">
      <div className="flex items-end justify-between gap-3">
        <h2 id="route-title" className="title-section">
          Your route
        </h2>
        <Link href="/app/agent/customers" className="text-[13px] text-dim hover:text-ink">
          All customers
        </Link>
      </div>
      <Segmented<View>
        label="Which customers"
        value={view}
        onChange={(next) => void setView(next)}
        block
        options={[
          { value: "overdue", label: "Overdue", count: overdue.data?.count },
          { value: "today", label: "Due today", count: dueToday.data?.count },
          { value: "all", label: "All" },
        ]}
      />
      {route.isPending ? (
        <CardListSkeleton count={4} />
      ) : route.isError ? (
        <ErrorState error={route.error} onRetry={() => void route.refetch()} bordered compact />
      ) : route.data.results.length === 0 ? (
        <EmptyState
          bordered
          compact
          illustration="settled"
          title={view === "overdue" ? "Nobody is overdue." : view === "today" ? "Nothing falls due today." : "No customers assigned yet."}
          description={view === "all" ? "Your branch manager assigns customers to you." : "Check the other tabs for upcoming dues."}
        />
      ) : (
        <ul className="rows-enter divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raised">
          {route.data.results.map((customer) => (
            <li key={customer.id}>
              <CustomerRow customer={customer} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Journey() {
  const lifecycle = useQuery(dashboardQueries.lifecycle());
  return (
    <SectionCard eyebrow="This month" title="Where your collections are">
      {lifecycle.isPending ? (
        <ChartSkeleton height={200} className="border-0 p-0" />
      ) : lifecycle.isError ? (
        <ErrorState error={lifecycle.error} onRetry={() => void lifecycle.refetch()} compact />
      ) : (
        <LifecycleFunnel lifecycle={lifecycle.data} />
      )}
    </SectionCard>
  );
}

function ModeSplit({ summary }: { summary: DashboardSummary }) {
  const { cash, upi } = summary.collected;
  const cashShare = moneyRatio(cash.amount, summary.collected.amount);
  return (
    <SectionCard eyebrow="This month" title="How customers paid">
      <div className="flex flex-col gap-4">
        <div className="flex h-2 overflow-hidden rounded-full bg-sunk" aria-hidden>
          <div className="bg-ink transition-[width] duration-700" style={{ width: `${cashShare * 100}%` }} />
          <div className="bg-st-upi transition-[width] duration-700" style={{ width: `${(1 - cashShare) * 100}%` }} />
        </div>
        <dl className="grid grid-cols-2 gap-4">
          {[
            { label: "Cash", tally: cash, dot: "bg-ink" },
            { label: "UPI", tally: upi, dot: "bg-st-upi" },
          ].map((row) => (
            <div key={row.label} className="flex flex-col gap-1">
              <dt className="flex items-center gap-2 text-[12.5px] text-dim">
                <span aria-hidden className={`size-1.5 rounded-full ${row.dot}`} />
                {row.label}
              </dt>
              <dd className="flex flex-col">
                <Money value={row.tally.amount} whole className="text-[18px] font-medium tracking-[-0.01em] text-ink" />
                <span className="text-[12px] text-faint">{countOf(row.tally.count, "receipt")}</span>
              </dd>
            </div>
          ))}
        </dl>
        {isZero(upi.amount) && (
          <p className="text-[12.5px] leading-relaxed text-dim">
            UPI payments never enter your cash in hand. Offer it when a customer has no cash ready.
          </p>
        )}
      </div>
    </SectionCard>
  );
}

function RecentReceipts() {
  const recent = useQuery(collectionQueries.list({ page_size: 5, ordering: "-collected_at" }));
  return (
    <SectionCard
      eyebrow="Latest"
      title="Recent receipts"
      flush
      actions={
        <Link href="/app/agent/collections" className="text-[12.5px] text-dim hover:text-ink">
          History
        </Link>
      }
    >
      {recent.isPending ? (
        <CardListSkeleton count={3} className="border-0 p-2" />
      ) : recent.isError ? (
        <ErrorState error={recent.error} onRetry={() => void recent.refetch()} compact />
      ) : recent.data.results.length === 0 ? (
        <EmptyState compact title="No receipts yet." />
      ) : (
        <ul className="divide-y divide-rule">
          {recent.data.results.map((item) => (
            <li key={item.id}>
              <Link href={`/app/agent/receipts/${item.id}`} className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-sunk/50">
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="truncate text-[13.5px] text-ink">{item.customer_name}</span>
                  <span className="truncate text-[11.5px] text-faint">
                    {formatRelative(item.collected_at)} · {formatTime(item.collected_at)}
                  </span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-1">
                  <Money value={item.amount} strike={item.status === "VOIDED"} className="text-[13.5px] text-ink" />
                  <span className="flex items-center gap-1.5">
                    <ModeChip mode={item.mode} />
                    <StatusChip kind="collection" status={item.status} size="sm" />
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
