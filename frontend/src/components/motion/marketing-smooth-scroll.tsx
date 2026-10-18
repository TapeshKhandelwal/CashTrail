"use client";

import { useEffect } from "react";

/** Gap kept between the fixed header and an anchored heading. */
const ANCHOR_GAP_PX = 28;

/**
 * Inertial scrolling for the marketing page only (never mount it inside /app). Lenis loads
 * lazily after hydration. In-page links, written "#id" or "/#id", are handled here with an
 * offset measured from the fixed header; a section can mark its heading with `data-anchor` so
 * the jump lands on the heading rather than the section's top padding.
 */
export function MarketingSmoothScroll() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let cancelled = false;
    let cleanup: (() => void) | undefined;

    void import("lenis").then(({ default: Lenis }) => {
      if (cancelled) return;
      const lenis = new Lenis({ duration: 1.05, smoothWheel: true, autoRaf: true });

      const offset = () => -((document.querySelector("header")?.getBoundingClientRect().height ?? 64) + ANCHOR_GAP_PX);
      const targetOf = (hash: string) => {
        const section = document.getElementById(decodeURIComponent(hash.slice(1)));
        return (section?.querySelector<HTMLElement>("[data-anchor]") ?? section) || null;
      };

      const onClick = (event: MouseEvent) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
        const link = (event.target as Element | null)?.closest?.("a[href*='#']");
        const href = link?.getAttribute("href");
        if (!href) return;
        const url = new URL(href, window.location.href);
        if (url.origin !== window.location.origin || url.pathname !== window.location.pathname || url.hash.length < 2) {
          return;
        }
        const target = targetOf(url.hash);
        if (!target) return;
        event.preventDefault();
        lenis.scrollTo(target, { offset: offset() });
        history.pushState(null, "", url.hash);
      };
      document.addEventListener("click", onClick);

      if (window.location.hash.length > 1) {
        const target = targetOf(window.location.hash);
        if (target) requestAnimationFrame(() => lenis.scrollTo(target, { offset: offset(), immediate: true }));
      }

      cleanup = () => {
        document.removeEventListener("click", onClick);
        lenis.destroy();
      };
    });

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, []);

  return null;
}
