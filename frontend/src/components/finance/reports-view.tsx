"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, Loader2 } from "lucide-react";
import { parseAsString, parseAsStringLiteral, useQueryStates } from "nuqs";

import { DateRangeFilter } from "@/components/data-table/date-range-filter";
import { FacetedFilter } from "@/components/data-table/faceted-filter";
import { EmptyState } from "@/components/feedback/empty-state";
import { ErrorState } from "@/components/feedback/error-state";
import { TableSkeleton } from "@/components/feedback/skeletons";
import { PageHeader } from "@/components/layout/page-header";
import { Money } from "@/components/money/money";
import { resolveStatus, StatusChip, type StatusInput } from "@/components/status/status-chip";
import { Button } from "@/components/ui/button";
import { REPORTS, reportQueries, useDownloadReport } from "@/features/reports/api";
import { useBranchScope } from "@/hooks/use-branch-scope";
import type { FilterOption } from "@/hooks/use-data-table-state";
import { COLLECTION_STATUS_OPTIONS, useAgentOptions, useBranchOptions } from "@/hooks/use-filter-options";
import { formatDate, formatDateTime } from "@/lib/dates";
import { countOf } from "@/lib/format";
import { depositStatus, discrepancyStatus, PAYMENT_MODE, submissionStatus, type StatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";
import {
  DISCREPANCY_KIND_LABEL,
  DISCREPANCY_REASON_LABEL,
  type DepositStatus,
  type DiscrepancyKind,
  type DiscrepancyReasonCode,
  type DiscrepancyStatus,
  type PaymentMode,
  type ReportName,
  type ReportParams,
  type SubmissionStatus,
} from "@/types/domain";

const NAMES = REPORTS.map((report) => report.name) as [ReportName, ...ReportName[]];

export function ReportsView() {
  const { branch, canSwitch, setBranch } = useBranchScope();
  const [values, setValues] = useQueryStates(
    {
      report: parseAsStringLiteral(NAMES).withDefault("collections"),
      date_from: parseAsString,
      date_to: parseAsString,
      agent: parseAsString,
      status: parseAsString,
    },
    { history: "replace" },
  );
  const branches = useBranchOptions(canSwitch);
  const agents = useAgentOptions(branch ?? undefined);
  const params: ReportParams = {
    ...(values.date_from ? { date_from: values.date_from } : {}),
    ...(values.date_to ? { date_to: values.date_to } : {}),
    ...(branch && canSwitch ? { branch } : {}),
    ...(values.agent ? { agent: Number(values.agent) } : {}),
    ...(values.status ? { status: values.status } : {}),
  };
  const preview = useQuery(reportQueries.preview(values.report, params));
  const download = useDownloadReport();
  const active = REPORTS.find((report) => report.name === values.report) ?? REPORTS[0];

  return (
    <>
      <PageHeader
        eyebrow="Finance · Control"
        title="Reports"
        description="Exports for audit and the books. What you see below is exactly what downloads."
        actions={
          <Button disabled={download.isPending} onClick={() => download.mutate({ name: values.report, params })}>
            {download.isPending ? <Loader2 className="animate-spin" /> : <Download data-icon="inline-start" />}
            Download CSV
          </Button>
        }
      />
      <div className="grid items-start gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <nav aria-label="Reports" className="flex flex-col overflow-hidden rounded-xl border border-rule bg-raised">
          {REPORTS.map((report) => (
            <button
              key={report.name}
              type="button"
              aria-current={report.name === values.report ? "page" : undefined}
              // Each report has its own statuses, so a status chosen for another one is dropped.
              onClick={() => void setValues({ report: report.name, status: null })}
              className={cn(
                "flex flex-col gap-0.5 border-b border-rule px-4 py-3.5 text-left transition-colors last:border-b-0 hover:bg-sunk/60",
                report.name === values.report && "bg-brand-tint shadow-[inset_2px_0_0_var(--brand)]",
              )}
            >
              <span className="text-[14px] text-ink">{report.title}</span>
              <span className={cn("text-[12.5px] leading-snug text-dim", report.name !== values.report && "max-sm:hidden")}>{report.description}</span>
            </button>
          ))}
        </nav>

        <div className="flex min-w-0 flex-col gap-4">
          <div
            role="search"
            aria-label="Report filters"
            className="flex flex-wrap items-center gap-2 max-sm:-my-1.5 max-sm:flex-nowrap max-sm:scrollbar-none max-sm:overflow-x-auto max-sm:py-1.5 max-sm:pr-6 max-sm:mask-r-from-[calc(100%-1.5rem)]"
          >
            {/* With no range the server reports the month to date, so the chip says so. */}
            <DateRangeFilter
              label="This month"
              value={{ from: values.date_from ?? undefined, to: values.date_to ?? undefined }}
              onChange={(range) => void setValues({ date_from: range.from, date_to: range.to })}
            />
            {canSwitch && (
              <FacetedFilter
                label="Branch"
                single
                options={branches}
                selected={branch ? [String(branch)] : []}
                onChange={(next) => setBranch(next[0] ? Number(next[0]) : null)}
              />
            )}
            <FacetedFilter
              label="Agent"
              single
              options={agents}
              selected={values.agent ? [values.agent] : []}
              onChange={(next) => void setValues({ agent: next[0] ?? null })}
            />
            <FacetedFilter
              label="Status"
              single
              options={STATUS_OPTIONS[values.report]}
              selected={values.status ? [values.status] : []}
              onChange={(next) => void setValues({ status: next[0] ?? null })}
            />
          </div>
          {preview.isPending ? (
            <TableSkeleton rows={8} columns={6} />
          ) : preview.isError ? (
            <ErrorState error={preview.error} onRetry={() => void preview.refetch()} bordered />
          ) : preview.data.rows.length === 0 ? (
            <EmptyState bordered title="No rows for these filters." />
          ) : (
            <div className="@container overflow-hidden rounded-xl border border-rule bg-raised">
              <div className="overflow-auto @max-2xl:hidden">
                <table className="w-full text-[12.5px]">
                  <caption className="sr-only">{active.title} preview</caption>
                  <thead className="sticky top-0 bg-sunk">
                    <tr>
                      {preview.data.headers.map((header, index) => (
                        <th
                          key={header}
                          scope="col"
                          className={cn(
                            "h-9 px-3 text-left font-mono text-[10.5px] font-normal tracking-[0.1em] whitespace-nowrap text-faint uppercase",
                            preview.data.rows.some((row) => AMOUNT.test(row[index] ?? "")) && "text-right",
                          )}
                        >
                          {header.replaceAll("_", " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule">
                    {preview.data.rows.map((row, index) => (
                      <tr key={index}>
                        {row.map((cell, cellIndex) => (
                          <td key={cellIndex} className={cn("h-9 px-3 whitespace-nowrap text-ink", AMOUNT.test(cell) && "text-right tabular-nums")}>
                            <ReportCell report={values.report} header={preview.data.headers[cellIndex] ?? ""} value={cell} row={toRecord(preview.data.headers, row)} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul className="divide-y divide-rule @2xl:hidden">
                {preview.data.rows.map((row, index) => (
                  <li key={index}>
                    <ReportCard report={values.report} record={toRecord(preview.data.headers, row)} />
                  </li>
                ))}
              </ul>
              <p className="border-t border-rule bg-sunk/60 px-4 py-2.5 text-[12.5px] text-dim">Showing the first {countOf(preview.data.rows.length, "row")}. The download has every row.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

const options = <T extends string>(statuses: readonly T[], meta: (status: T) => StatusMeta): FilterOption[] =>
  statuses.map((status) => ({ value: status, label: meta(status).label }));

/** The statuses each report narrows to; the server checks them per report. */
const STATUS_OPTIONS: Record<ReportName, FilterOption[]> = {
  collections: COLLECTION_STATUS_OPTIONS,
  submissions: options<SubmissionStatus>(["SUBMITTED", "APPROVED", "APPROVED_WITH_DISCREPANCY", "REJECTED"], submissionStatus),
  deposits: options<DepositStatus>(["PENDING", "SETTLED", "SETTLED_WITH_MISMATCH", "FAILED"], depositStatus),
  discrepancies: options<DiscrepancyStatus>(["OPEN", "RESOLVED", "WRITTEN_OFF"], discrepancyStatus),
};

const AMOUNT = /^-?\d+\.\d{2}$/;
const TIMESTAMP = /^\d{4}-\d{2}-\d{2}T/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

type ReportRecord = Record<string, string>;

const toRecord = (headers: string[], row: string[]): ReportRecord =>
  Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""]));

/** Phone cards: the reference, its status and headline amount, then the four facts that identify the row. */
const CARD: Record<ReportName, { title: string; amount: string; facts: string[] }> = {
  collections: { title: "Receipt number", amount: "Amount", facts: ["Customer name", "Collected at", "Mode", "Agent", "Branch"] },
  submissions: { title: "Submission number", amount: "Declared amount", facts: ["Agent", "Submitted at", "Received amount", "Difference", "Branch"] },
  deposits: { title: "Deposit number", amount: "Deposited amount", facts: ["Bank account", "Deposit date", "Settled amount", "Branch", "Source"] },
  discrepancies: { title: "Kind", amount: "Amount", facts: ["Raised at", "Submission number", "Deposit number", "Agent", "Branch", "Reason code"] },
};

function statusInput(report: ReportName, row: ReportRecord): StatusInput | null {
  const status = row.Status;
  if (!status) return null;
  switch (report) {
    case "collections":
      return { kind: "collection", status } as StatusInput;
    case "submissions":
      return { kind: "submission", status, difference: row.Difference || null } as StatusInput;
    case "deposits":
      return { kind: "deposit", status, isDelayed: row.Delayed === "yes", daysPending: Number(row["Days pending"]) || null } as StatusInput;
    case "discrepancies":
      return { kind: "discrepancy", status, direction: row.Direction || undefined } as StatusInput;
  }
}

/** The CSV value as the rest of the app shows it: dates in IST, rupees grouped, statuses as dot and label. */
function ReportCell({ report, header, value, row }: { report: ReportName; header: string; value: string; row: ReportRecord }) {
  if (!value) return <span className="text-faint">—</span>;
  if (header === "Status") {
    const input = statusInput(report, row);
    const meta = input ? resolveStatus(input) : undefined;
    if (meta) return <StatusChip kind="custom" meta={meta} />;
  }
  if (header === "Kind") return <>{DISCREPANCY_KIND_LABEL[value as DiscrepancyKind] ?? value}</>;
  if (header === "Reason code") return <>{DISCREPANCY_REASON_LABEL[value as DiscrepancyReasonCode] ?? value}</>;
  if (header === "Mode") return <>{PAYMENT_MODE[value as PaymentMode]?.label ?? value}</>;
  if (AMOUNT.test(value)) return <Money value={value} />;
  if (TIMESTAMP.test(value)) return <span className="tabular-nums">{formatDateTime(value)}</span>;
  if (DATE.test(value)) return <span className="tabular-nums">{formatDate(value)}</span>;
  if (/(number|reference|ID)$/.test(header)) return <span className="font-mono text-[12px]">{value}</span>;
  return <>{value}</>;
}

function ReportCard({ report, record }: { report: ReportName; record: ReportRecord }) {
  const card = CARD[report];
  const facts = card.facts.filter((header) => record[header]).slice(0, 4);
  const cell = (header: string) => <ReportCell report={report} header={header} value={record[header] ?? ""} row={record} />;

  return (
    <div className="flex flex-col gap-3 px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col items-start gap-1.5">
          <span className={cn("max-w-full truncate text-ink", report === "discrepancies" ? "text-[14px] font-medium" : "font-mono text-[13px]")}>
            {cell(card.title)}
          </span>
          {record.Status && cell("Status")}
        </div>
        <span className="shrink-0 text-right text-[15px] font-medium text-ink tabular-nums">{cell(card.amount)}</span>
      </div>
      {facts.length > 0 && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-[13px] [&>:last-child:nth-child(odd)]:col-span-2">
          {facts.map((header) => (
            <div key={header} className="flex min-w-0 flex-col gap-0.5">
              <dt className="font-mono text-[10px] tracking-[0.12em] text-faint uppercase">{header}</dt>
              <dd className="text-ink wrap-anywhere">{cell(header)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
