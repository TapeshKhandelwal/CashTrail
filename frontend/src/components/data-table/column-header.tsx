"use client";

import type { Header, RowData } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { DataTableFeatures } from "./data-table-features";

/** Sortable header button; the table maps sorting to the backend `ordering` param. */
export function ColumnHeader<TData extends RowData>({
  header,
  children,
}: {
  header: Header<DataTableFeatures, TData, unknown>;
  children: ReactNode;
}) {
  const column = header.column;
  const end = column.columnDef.meta?.align === "end";
  if (!column.getCanSort()) {
    return <span className={cn("flex", end && "justify-end")}>{children}</span>;
  }
  const sorted = column.getIsSorted();
  const Icon = sorted === "asc" ? ArrowUp : sorted === "desc" ? ArrowDown : ArrowUpDown;
  return (
    <button
      type="button"
      onClick={column.getToggleSortingHandler()}
      className={cn(
        "-mx-1.5 inline-flex h-7 items-center gap-1 rounded-md px-1.5 uppercase transition-colors outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-focus",
        end && "ml-auto flex-row-reverse",
        sorted && "text-ink",
      )}
    >
      {children}
      <Icon className={cn("size-3", !sorted && "opacity-40")} aria-hidden />
    </button>
  );
}
