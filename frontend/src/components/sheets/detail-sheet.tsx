"use client";

import type { ReactNode } from "react";

import { BottomSheet } from "@/components/sheets/bottom-sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useIsMobile } from "@/hooks/use-mobile";
import { cn } from "@/lib/utils";

interface OverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

/**
 * Row detail: a 480px right-hand Sheet on desktop, an expandable bottom sheet on phones.
 *
 *   <DetailSheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)} title="SUB-2291">…</DetailSheet>
 */
export function DetailSheet({ open, onOpenChange, title, description, children, footer, className }: OverlayProps) {
  const isMobile = useIsMobile();
  if (isMobile) {
    return (
      <BottomSheet open={open} onOpenChange={onOpenChange} title={title} description={description} footer={footer} expandable>
        {children}
      </BottomSheet>
    );
  }
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className={cn("w-full gap-0 border-rule bg-raised sm:max-w-[480px]", className)}>
        <SheetHeader className="border-b border-rule px-6 py-5 pr-12">
          <SheetTitle>{title}</SheetTitle>
          {description && <SheetDescription>{description}</SheetDescription>}
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <SheetFooter className="border-t border-rule bg-sunk/60 px-6 py-4">{footer}</SheetFooter>}
      </SheetContent>
    </Sheet>
  );
}

/**
 * Form dialogs (settle, resolve, create customer): a centred Dialog on desktop and a
 * keyboard-aware bottom sheet on phones.
 */
export function ResponsiveDialog({ open, onOpenChange, title, description, children, footer, className }: OverlayProps) {
  const isMobile = useIsMobile();
  if (isMobile) {
    return (
      <BottomSheet
        open={open}
        onOpenChange={onOpenChange}
        title={title}
        description={description}
        footer={footer}
        keyboardAware
      >
        {children}
      </BottomSheet>
    );
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("gap-5 sm:max-w-lg", className)}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <div className="max-h-[70dvh] overflow-y-auto">{children}</div>
        {footer && <DialogFooter>{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}
