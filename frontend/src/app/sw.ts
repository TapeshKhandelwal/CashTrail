/// <reference lib="esnext" />
/// <reference lib="webworker" />
import type { PrecacheEntry, SerwistGlobalConfig } from "serwist";
import { CacheFirst, ExpirationPlugin, NetworkFirst, NetworkOnly, Serwist, StaleWhileRevalidate } from "serwist";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}
declare const self: ServiceWorkerGlobalScope;

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api").origin;
const DAY = 60 * 60 * 24;

/*
 * Financial data is never cached: API calls (Django and the BFF), RSC payloads and app HTML
 * always go to the network. Only immutable build assets, images, fonts and the public landing
 * page are cached. Mutations have no route, so they always hit the network (Idempotency-Key
 * makes retries safe).
 */
const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  // Activated only when the user accepts the update toast.
  skipWaiting: false,
  clientsClaim: true,
  navigationPreload: true,
  disableDevLogs: true,
  runtimeCaching: [
    {
      matcher: ({ url }) => url.origin === API_ORIGIN || url.pathname.startsWith("/api/"),
      handler: new NetworkOnly(),
    },
    { matcher: ({ request }) => request.headers.get("RSC") === "1", handler: new NetworkOnly() },
    {
      matcher: ({ request, url, sameOrigin }) => sameOrigin && request.mode === "navigate" && url.pathname === "/",
      handler: new NetworkFirst({
        cacheName: "marketing-pages",
        networkTimeoutSeconds: 4,
        plugins: [new ExpirationPlugin({ maxEntries: 4, maxAgeSeconds: 7 * DAY })],
      }),
    },
    { matcher: ({ request }) => request.mode === "navigate", handler: new NetworkOnly() },
    {
      matcher: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith("/_next/static/"),
      handler: new CacheFirst({
        cacheName: "next-static",
        plugins: [new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 30 * DAY, maxAgeFrom: "last-used" })],
      }),
    },
    {
      matcher: ({ request, sameOrigin }) => sameOrigin && request.destination === "image",
      handler: new StaleWhileRevalidate({
        cacheName: "images",
        plugins: [new ExpirationPlugin({ maxEntries: 120, maxAgeSeconds: 30 * DAY, maxAgeFrom: "last-used" })],
      }),
    },
    {
      matcher: ({ request }) => request.destination === "font",
      handler: new CacheFirst({
        cacheName: "fonts",
        plugins: [new ExpirationPlugin({ maxEntries: 16, maxAgeSeconds: 365 * DAY })],
      }),
    },
  ],
  fallbacks: {
    entries: [{ url: "/~offline", matcher: ({ request }) => request.destination === "document" }],
  },
});

// Logout or role switch: drop every runtime cache, keep the precache.
self.addEventListener("message", (event) => {
  if (event.data?.type === "CLEAR_RUNTIME_CACHES") {
    event.waitUntil(
      caches
        .keys()
        .then((keys) => Promise.all(keys.filter((key) => !key.includes("precache")).map((key) => caches.delete(key)))),
    );
  }
});

serwist.addEventListeners();
