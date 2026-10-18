"use client";

import { LazyMotion, MotionConfig } from "motion/react";
import type { ReactNode } from "react";

import { transition } from "@/lib/motion";

const loadFeatures = () => import("./motion-features").then((module) => module.default);

/**
 * JS motion for the app and login: features load lazily, and with `strict` any `motion.*`
 * component throws, so app code uses `m.*`. Prefer the CSS motion classes; reach for `m` only
 * for presence (exit) and layout animations.
 */
export function MotionProvider({ children, strict = true }: { children: ReactNode; strict?: boolean }) {
  return (
    <LazyMotion features={loadFeatures} strict={strict}>
      <MotionConfig reducedMotion="user" transition={transition.ui}>
        {children}
      </MotionConfig>
    </LazyMotion>
  );
}
