import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-lg border border-input bg-raised px-2.5 py-2 text-base transition-colors outline-none placeholder:text-faint focus-visible:border-ink focus-visible:ring-3 focus-visible:ring-focus disabled:cursor-not-allowed disabled:bg-input/50 disabled:opacity-50 aria-invalid:border-danger aria-invalid:ring-3 aria-invalid:ring-danger/15 md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
