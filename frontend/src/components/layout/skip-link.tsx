export const MAIN_CONTENT_ID = "main-content";

/** First focusable element: jumps keyboard users past the navigation. */
export function SkipLink() {
  return (
    <a
      href={`#${MAIN_CONTENT_ID}`}
      className="sr-only z-[70] rounded-lg bg-ink px-4 py-2 text-[13.5px] text-paper focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
    >
      Skip to content
    </a>
  );
}
