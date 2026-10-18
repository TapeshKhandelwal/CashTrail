"use client";

import { Drawer } from "@base-ui/react/drawer";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface BottomSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  /** Sticky footer (primary action); sits above the home indicator. */
  footer?: ReactNode;
  /** Half-height peek that drags up to full screen (detail views). Off for forms. */
  expandable?: boolean;
  /** Keeps focused fields above the on-screen keyboard (amount entry, remarks). */
  keyboardAware?: boolean;
  className?: string;
}

/**
 * Mobile bottom sheet on Base UI Drawer: drag to dismiss, backdrop follows the drag, snap points
 * [0.5, 1] when `expandable`. Use `DetailSheet` to get a right-hand Sheet on desktop instead.
 */
export function BottomSheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  expandable = false,
  keyboardAware = false,
  className,
}: BottomSheetProps) {
  const portal = (
    <Drawer.Portal>
      <Drawer.Backdrop
        className={cn(
          "fixed inset-0 z-50 bg-scrim",
          "opacity-[calc(1-var(--drawer-swipe-progress,0))] transition-opacity duration-300",
          "data-[starting-style]:opacity-0 data-[ending-style]:opacity-0",
        )}
      />
      <Drawer.Viewport className="fixed inset-x-0 bottom-0 z-50 flex justify-center">
        <Drawer.Popup
          className={cn(
            "flex w-full max-w-[640px] flex-col rounded-t-2xl border border-b-0 border-rule bg-raised text-ink shadow-float outline-none",
            expandable ? "h-[calc(100dvh-env(safe-area-inset-top)-0.5rem)]" : "max-h-[calc(100dvh-env(safe-area-inset-top)-0.5rem)]",
            "[transform:translateY(calc(var(--drawer-snap-point-offset,0px)+var(--drawer-swipe-movement-y,0px)))]",
            "transition-transform duration-[420ms] ease-out-expo data-[swiping]:duration-0",
            "data-[starting-style]:[transform:translateY(100%)] data-[ending-style]:[transform:translateY(100%)]",
            className,
          )}
        >
          <div aria-hidden className="mx-auto mt-2.5 mb-1 h-1 w-9 shrink-0 rounded-full bg-rule-strong" />
          <Drawer.Content className="flex min-h-0 flex-1 flex-col">
            <div className="flex flex-col gap-1 px-5 pt-2 pb-3">
              <Drawer.Title className="font-display text-[22px] leading-tight text-ink">{title}</Drawer.Title>
              {description && (
                <Drawer.Description className="text-[13.5px] text-dim">{description}</Drawer.Description>
              )}
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[calc(var(--drawer-keyboard-inset,0px)+1rem)]">
              {children}
            </div>
            {footer && (
              <div className="border-t border-rule bg-raised px-5 pt-3 pb-safe-offset-3 *:data-[slot=button]:w-full **:data-[slot=button]:min-h-11">
                {footer}
              </div>
            )}
            {!footer && <div className="pb-safe" />}
          </Drawer.Content>
        </Drawer.Popup>
      </Drawer.Viewport>
    </Drawer.Portal>
  );

  return (
    <Drawer.Root
      open={open}
      onOpenChange={(next) => onOpenChange(next)}
      snapPoints={expandable ? [0.5, 1] : undefined}
      defaultSnapPoint={expandable ? 0.5 : undefined}
    >
      {keyboardAware ? <Drawer.VirtualKeyboardProvider>{portal}</Drawer.VirtualKeyboardProvider> : portal}
    </Drawer.Root>
  );
}
