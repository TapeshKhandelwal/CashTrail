"use client";

import { useSyncExternalStore } from "react";

const STANDALONE_QUERY = "(display-mode: standalone), (display-mode: minimal-ui), (display-mode: fullscreen)";

function subscribeStandalone(callback: () => void) {
  const query = window.matchMedia(STANDALONE_QUERY);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function isStandalone(): boolean {
  return (
    window.matchMedia(STANDALONE_QUERY).matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export const useIsStandalone = () => useSyncExternalStore(subscribeStandalone, isStandalone, () => false);

export type Platform = "ios" | "android" | "desktop";

export function getPlatform(): Platform {
  const agent = navigator.userAgent;
  // iPadOS reports itself as a Mac; touch support gives it away.
  const iPadOS = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
  if (/iPhone|iPad|iPod/.test(agent) || iPadOS) return "ios";
  if (/Android/.test(agent)) return "android";
  return "desktop";
}

export interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
  prompt(): Promise<void>;
}

// Captured at module load so the event is not missed before React mounts.
let deferredPrompt: BeforeInstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((listener) => listener());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event as BeforeInstallPromptEvent;
    emit();
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    emit();
  });
}

export const useInstallPromptEvent = () =>
  useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => deferredPrompt,
    () => null,
  );

export async function promptInstall(): Promise<"accepted" | "dismissed" | "unavailable"> {
  if (!deferredPrompt) return "unavailable";
  await deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  emit();
  return outcome;
}

/** Called on logout and role switch so no cached response outlives the session. */
export function clearRuntimeCaches(): void {
  navigator.serviceWorker?.controller?.postMessage({ type: "CLEAR_RUNTIME_CACHES" });
}

/** Opens the install prompt from anywhere (avatar menu, landing CTA). */
export const INSTALL_EVENT = "cashtrail:install";
export function requestInstallPrompt(): void {
  window.dispatchEvent(new Event(INSTALL_EVENT));
}

const ELIGIBLE_KEY = "ct.install.eligible";
const SESSIONS_KEY = "ct.install.sessions";
const COUNTED_KEY = "ct.install.counted";
const SNOOZE_KEY = "ct.install.snoozedAt";
const SNOOZE_MS = 14 * 24 * 60 * 60 * 1000;

function readStorage(storage: () => Storage, key: string): string | null {
  try {
    return storage().getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(storage: () => Storage, key: string, value: string): void {
  try {
    storage().setItem(key, value);
  } catch {
    // Private mode or blocked storage: the prompt simply shows less often.
  }
}

const local = () => window.localStorage;
const session = () => window.sessionStorage;

/** Call after a meaningful moment (an agent's first recorded collection) to allow the install card. */
export function markInstallMoment(): void {
  writeStorage(local, ELIGIBLE_KEY, "1");
  window.dispatchEvent(new Event(`${INSTALL_EVENT}:eligible`));
}

/** Counts app sessions once per tab; the second session makes the install card eligible. */
export function isInstallEligible(): boolean {
  if (!readStorage(session, COUNTED_KEY)) {
    writeStorage(session, COUNTED_KEY, "1");
    writeStorage(local, SESSIONS_KEY, String(Number(readStorage(local, SESSIONS_KEY) ?? 0) + 1));
  }
  const snoozedAt = Number(readStorage(local, SNOOZE_KEY) ?? 0);
  if (Date.now() - snoozedAt < SNOOZE_MS) return false;
  return readStorage(local, ELIGIBLE_KEY) === "1" || Number(readStorage(local, SESSIONS_KEY) ?? 0) >= 2;
}

export function snoozeInstallPrompt(): void {
  writeStorage(local, SNOOZE_KEY, String(Date.now()));
}
