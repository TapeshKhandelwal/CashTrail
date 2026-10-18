"use client";

import { useTheme } from "next-themes";
import { useEffect } from "react";

const THEME_COLOR = { light: "#FBFAF7", dark: "#0F1012" } as const;

/** Keeps the browser/status-bar colour in step when the user overrides the OS theme. */
export function ThemeColorSync() {
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (resolvedTheme !== "light" && resolvedTheme !== "dark") return;
    document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
      meta.setAttribute("content", THEME_COLOR[resolvedTheme]);
      meta.removeAttribute("media");
    });
  }, [resolvedTheme]);

  return null;
}
