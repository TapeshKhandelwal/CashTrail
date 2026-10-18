"use client";

import { useEffect } from "react";

const SELECTOR = ".reveal, .reveal-lift, .reveal-blur, .reveal-mask, .stagger";
const STAGGER_STEP_S = 0.075;
const STAGGER_CAP = 7;
const FAILSAFE_MS = 2500;

/**
 * One IntersectionObserver for every entrance class (`reveal`, `reveal-lift`, `reveal-blur`,
 * `reveal-mask`, `stagger`). Mount once per page tree; elements rendered later are picked up too.
 *
 * Hiding is opt-in: `html.js-reveal` is only added here, so without JS (or with reduced
 * motion) everything renders visible. A failsafe reveals anything on screen that the observer
 * has not reached after 2.5s.
 */
export function RevealObserver() {
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const root = document.documentElement;
    root.classList.add("js-reveal");

    // Children cascade by index; past seven they arrive together so the row never lags.
    const reveal = (element: Element) => {
      if (element.classList.contains("stagger")) {
        Array.from(element.children).forEach((child, index) => {
          (child as HTMLElement).style.setProperty(
            "--reveal-delay",
            `${Math.min(index, STAGGER_CAP) * STAGGER_STEP_S}s`,
          );
        });
      }
      element.classList.add("is-in");
    };

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          reveal(entry.target);
          io.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.08 },
    );

    const observeAll = (scope: ParentNode) => {
      scope.querySelectorAll(SELECTOR).forEach((element) => {
        if (!element.classList.contains("is-in")) io.observe(element);
      });
    };
    observeAll(document);

    let frame = 0;
    const mutations = new MutationObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => observeAll(document));
    });
    mutations.observe(document.body, { childList: true, subtree: true });

    const failsafe = window.setTimeout(() => {
      document.querySelectorAll(SELECTOR).forEach((element) => {
        if (!element.classList.contains("is-in") && element.getBoundingClientRect().top < window.innerHeight) {
          reveal(element);
        }
      });
    }, FAILSAFE_MS);

    return () => {
      window.clearTimeout(failsafe);
      cancelAnimationFrame(frame);
      mutations.disconnect();
      io.disconnect();
      root.classList.remove("js-reveal");
    };
  }, []);

  return null;
}
