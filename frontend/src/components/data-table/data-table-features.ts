import {
  columnVisibilityFeature,
  createColumnHelper,
  metaHelper,
  rowPaginationFeature,
  rowSelectionFeature,
  rowSortingFeature,
  tableFeatures,
  type RowData,
} from "@tanstack/react-table";

export interface DataTableColumnMeta {
  /** Header/label text used by view options and mobile cards when `header` isn't a string. */
  label?: string;
  /** Right-align (amounts); also applies tabular figures. */
  align?: "start" | "end";
  /** Set the cell in mono (receipt, submission and slip references). */
  mono?: boolean;
  /** Backend `ordering` field when it differs from the column id. */
  sortField?: string;
  /** Mobile card slots: the bold title, the status badge, the large amount. */
  card?: "title" | "badge" | "amount" | "hidden";
  /** Fixed column width class, e.g. "w-32". */
  width?: string;
}

/**
 * The single feature set for every data table. Data is server-processed: sorting and
 * pagination are manual, and the URL owns their state.
 */
export const dataTableFeatures = tableFeatures({
  rowSortingFeature,
  rowPaginationFeature,
  rowSelectionFeature,
  columnVisibilityFeature,
  columnMeta: metaHelper<DataTableColumnMeta>(),
});

export type DataTableFeatures = typeof dataTableFeatures;

/**
 * Column helper bound to the shared features.
 *
 *   const col = createColumns<Collection>();
 *   export const collectionColumns = col.columns([
 *     col.accessor("receipt_number", { header: "Receipt", meta: { card: "title", mono: true } }),
 *     col.accessor("amount", { header: "Amount", enableSorting: true, meta: { align: "end", card: "amount" },
 *       cell: ({ getValue }) => <Money value={getValue()} /> }),
 *   ]);
 */
export function createColumns<TData extends RowData>() {
  return createColumnHelper<DataTableFeatures, TData>();
}

export type DataTableColumns<TData extends RowData> = ReturnType<ReturnType<typeof createColumns<TData>>["columns"]>;
