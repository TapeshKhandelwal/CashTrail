"use client";

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PAGE_SIZES } from "@/hooks/use-data-table-state";
import { formatCount } from "@/lib/format";

interface TablePaginationProps {
  page: number;
  pageSize: number;
  rowCount: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

/** "Showing 1–25 of 312" + page size + pager. Pages are 1-based like the API. */
export function TablePagination({ page, pageSize, rowCount, onPageChange, onPageSizeChange }: TablePaginationProps) {
  const pageCount = Math.max(1, Math.ceil(rowCount / pageSize));
  const first = rowCount === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(rowCount, page * pageSize);

  return (
    <nav aria-label="Pagination" className="flex flex-wrap items-center justify-between gap-3 px-1 pt-1 font-mono text-[11px] tracking-[0.06em] text-faint uppercase">
      <p className="tabular-nums" aria-live="polite">
        Showing {formatCount(first)}–{formatCount(last)} of {formatCount(rowCount)}
      </p>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 max-sm:hidden">
          <span>Rows</span>
          <Select value={String(pageSize)} onValueChange={(value) => onPageSizeChange(Number(value))}>
            <SelectTrigger size="sm" className="w-[4.5rem] font-mono text-[12px]" aria-label="Rows per page">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <span className="tabular-nums max-sm:hidden">
          Page {formatCount(page)} of {formatCount(pageCount)}
        </span>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon-sm" className="max-sm:hidden" onClick={() => onPageChange(1)} disabled={page <= 1} aria-label="First page">
            <ChevronsLeft />
          </Button>
          <Button variant="outline" size="icon-sm" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon-sm" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount} aria-label="Next page">
            <ChevronRight />
          </Button>
          <Button variant="outline" size="icon-sm" className="max-sm:hidden" onClick={() => onPageChange(pageCount)} disabled={page >= pageCount} aria-label="Last page">
            <ChevronsRight />
          </Button>
        </div>
      </div>
    </nav>
  );
}
