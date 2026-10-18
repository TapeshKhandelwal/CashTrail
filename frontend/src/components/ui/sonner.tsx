"use client"

import { useTheme } from "next-themes"
import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

/** White card, hairline border, coloured icon only: toasts never flood colour. */
const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme()

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4 text-st-settled" />,
        info: <InfoIcon className="size-4 text-st-received" />,
        warning: <TriangleAlertIcon className="size-4 text-st-collected" />,
        error: <OctagonXIcon className="size-4 text-st-rejected" />,
        loading: <Loader2Icon className="size-4 animate-spin text-dim" />,
      }}
      style={
        {
          "--normal-bg": "var(--raised)",
          "--normal-text": "var(--ink)",
          "--normal-border": "var(--rule)",
          "--border-radius": "12px",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "font-sans !text-[13.5px] !shadow-float",
          title: "!font-medium",
          description: "!text-dim font-mono !text-[11.5px]",
          actionButton: "!bg-ink !text-paper !rounded-md !font-medium",
          cancelButton: "!bg-sunk !text-ink !rounded-md",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
