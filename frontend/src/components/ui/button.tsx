import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

import { Spinner } from "@/components/ui/spinner"

const buttonVariants = cva(
  "group/button hit-area relative inline-flex shrink-0 touch-manipulation items-center justify-center rounded-lg border border-transparent bg-clip-padding text-sm font-medium whitespace-nowrap transition-[color,background-color,border-color,box-shadow,transform] duration-150 ease-out-quint outline-none select-none focus-visible:ring-3 focus-visible:ring-focus active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-45 aria-busy:pointer-events-none aria-invalid:border-danger aria-invalid:ring-3 aria-invalid:ring-danger/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        /** Ink on paper: the one primary action on a surface. */
        default: "bg-ink text-paper hover:bg-ink-soft",
        /** White with a rule: secondary actions. */
        outline:
          "border-rule-strong bg-raised text-ink hover:border-ink/30 hover:bg-sunk aria-expanded:bg-sunk",
        secondary: "bg-sunk text-ink hover:bg-rule/70 aria-expanded:bg-rule/70",
        ghost: "text-dim hover:bg-sunk hover:text-ink aria-expanded:bg-sunk aria-expanded:text-ink",
        /** Rose text and rule; solid rose is reserved for confirm dialogs (`destructive-solid`). */
        destructive:
          "border-st-rejected/40 bg-raised text-st-rejected-fg hover:border-st-rejected hover:bg-st-rejected/6 focus-visible:ring-st-rejected/25",
        "destructive-solid":
          "bg-st-rejected text-white hover:bg-st-rejected/90 focus-visible:ring-st-rejected/30",
        link: "h-auto! border-0 p-0! text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink",
      },
      size: {
        default: "h-9 gap-2 px-3.5 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        xs: "h-7 gap-1 rounded-md px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-md px-3 text-[13px] has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2 [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-10 gap-2 px-4 text-[14.5px] has-data-[icon=inline-end]:pr-3.5 has-data-[icon=inline-start]:pl-3.5",
        /** Full-width mobile primary (sticky action bars). */
        xl: "h-12 gap-2.5 rounded-xl px-5 text-[15px] [&_svg:not([class*='size-'])]:size-[18px]",
        icon: "size-9",
        "icon-xs": "size-7 rounded-md [&_svg:not([class*='size-'])]:size-3.5",
        "icon-sm": "size-8 rounded-md",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    /** Shows a spinner in place of the label, keeps the width and sets aria-busy. */
    loading?: boolean
  }

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  if (asChild) {
    return (
      <Slot.Root
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </Slot.Root>
    )
  }

  return (
    <button
      // Only an explicit type="submit" submits a form; a stray button inside one must not.
      type="button"
      data-slot="button"
      data-variant={variant}
      data-size={size}
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {loading ? (
        <>
          <span className="invisible inline-flex items-center gap-[inherit]">{children}</span>
          <span className="absolute inset-0 flex items-center justify-center">
            <Spinner aria-label="Working" />
          </span>
        </>
      ) : (
        children
      )}
    </button>
  )
}

export { Button, buttonVariants, type ButtonProps }
