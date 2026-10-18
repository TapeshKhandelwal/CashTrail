import type { Transition } from "motion/react";

/**
 * Motion tokens for the few places that need JS animation (layout, presence). Everything else
 * is CSS: `ease-out-quint`, `ease-out-expo`, `ease-spring` utilities and the classes in
 * globals.css. Durations in seconds: UI 0.14–0.22, entrances 0.6–0.9.
 */
export const dur = { ui: 0.18, sheet: 0.2, enter: 0.72 } as const;

/** The same three curves as the CSS custom properties. */
export const ease = {
  outQuint: [0.22, 1, 0.36, 1],
  outExpo: [0.16, 1, 0.3, 1],
  spring: [0.34, 1.46, 0.64, 1],
} as const;

export const transition = {
  /** Small UI feedback: chips, segmented indicators, dot colour changes. */
  ui: { duration: dur.ui, ease: ease.outQuint },
  /** Dialogs and sheets. */
  sheet: { duration: dur.sheet, ease: ease.outQuint },
  /** Indicators that glide between items (active nav rail, tab underline). */
  glide: { type: "spring", stiffness: 520, damping: 42 },
} as const satisfies Record<string, Transition>;
