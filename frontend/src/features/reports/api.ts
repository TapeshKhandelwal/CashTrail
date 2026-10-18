import { queryOptions } from "@tanstack/react-query";
import { toast } from "sonner";

import { useApiMutation, type ApiMutationOptions } from "@/hooks/use-api";
import { api, saveFile, type Download } from "@/lib/api/client";
import { qk } from "@/lib/api/query-keys";
import { parseCsv } from "@/lib/csv";
import type { ReportName, ReportParams } from "@/types/domain";

export const REPORTS: { name: ReportName; title: string; description: string; supervisorsOnly?: boolean }[] = [
  { name: "collections", title: "Collections", description: "Every receipt with mode, status and lifecycle timestamps." },
  { name: "submissions", title: "Cash submissions", description: "Hand-overs with expected, declared and counted cash." },
  { name: "deposits", title: "Deposits & settlements", description: "Bank deposits, settlement credits and mismatches.", supervisorsOnly: true },
  { name: "discrepancies", title: "Discrepancies", description: "Shortages, excesses and mismatches with their resolution." },
];

export interface ReportPreview {
  headers: string[];
  rows: string[][];
}

export const reportQueries = {
  /** First `limit` rows of a report, parsed from the same CSV the download uses. */
  preview: (name: ReportName, params: ReportParams = {}, limit = 20) =>
    queryOptions({
      queryKey: qk.reports.preview(name, { ...params, limit }),
      queryFn: async ({ signal }): Promise<ReportPreview> => {
        const { blob } = await api.download(`reports/${name}.csv`, params, { signal });
        const [headers = [], ...rows] = parseCsv(await blob.text(), limit + 1);
        return { headers, rows };
      },
      staleTime: 60_000,
    }),
};

/** Downloads `reports/<name>.csv` and saves it with the server's filename. */
export function useDownloadReport(options?: ApiMutationOptions<Download, { name: ReportName; params?: ReportParams }>) {
  return useApiMutation(
    ({ name, params }: { name: ReportName; params?: ReportParams }) => api.download(`reports/${name}.csv`, params),
    {
      onSuccess: (file) => {
        saveFile(file);
        toast.success(`${file.filename} downloaded`);
      },
      ...options,
    },
  );
}
