import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/app",
    name: "CashTrail — Collections & Reconciliation",
    short_name: "CashTrail",
    description: "Record repayments, hand over cash and reconcile every rupee.",
    start_url: "/app?source=pwa",
    scope: "/",
    display: "standalone",
    display_override: ["standalone", "minimal-ui"],
    orientation: "portrait",
    background_color: "#FBFAF7",
    theme_color: "#FBFAF7",
    lang: "en-IN",
    dir: "ltr",
    categories: ["finance", "business", "productivity"],
    prefer_related_applications: false,
    launch_handler: { client_mode: ["navigate-existing", "auto"] },
    icons: [
      { src: "/icons/pwa-64x64.png", sizes: "64x64", type: "image/png" },
      { src: "/icons/pwa-192x192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      {
        name: "New collection",
        url: "/app/agent/collect",
        icons: [{ src: "/icons/pwa-192x192.png", sizes: "192x192" }],
      },
      { name: "Hand over cash", url: "/app/agent/handover" },
    ],
    screenshots: [
      { src: "/screenshots/agent-today.png", sizes: "1080x2340", type: "image/png", form_factor: "narrow", label: "Today: cash in hand and visits" },
      { src: "/screenshots/agent-receipt.png", sizes: "1080x2340", type: "image/png", form_factor: "narrow", label: "Instant digital receipt" },
      { src: "/screenshots/finance-dashboard.png", sizes: "2560x1600", type: "image/png", form_factor: "wide", label: "Finance dashboard" },
    ],
  };
}
