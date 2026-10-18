/**
 * Reading progress hairline at the top of a long page, driven by `animation-timeline: scroll()`
 * on the compositor. Where scroll timelines are unsupported it simply stays hidden.
 */
export function ScrollProgress() {
  return (
    <div
      aria-hidden
      className="scroll-progress pointer-events-none fixed inset-x-0 top-0 z-[60] h-px origin-left scale-x-0 bg-brand"
    />
  );
}
