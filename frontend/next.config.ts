import { withSerwist } from "@serwist/turbopack";
import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Camera is for deposit-slip photos; payment for the gateway's checkout frame (Cashfree).
  {
    key: "Permissions-Policy",
    value:
      'camera=(self), microphone=(), geolocation=(), payment=(self "https://sandbox.cashfree.com" "https://payments.cashfree.com" "https://api.cashfree.com" "https://sdk.cashfree.com")',
  },
  ...(process.env.NODE_ENV === "production"
    ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]
    : []),
];

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  experimental: {
    useOffline: true,
    authInterrupts: true,
  },
  // Landing photos are downloaded into /public, so no remote image hosts are allowed.
  images: {
    formats: ["image/avif", "image/webp"],
    qualities: [50, 60, 75],
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [
      {
        source: "/serwist/:path*",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Content-Type", value: "application/javascript; charset=utf-8" },
        ],
      },
      { source: "/(.*)", headers: securityHeaders },
    ];
  },
};

export default withSerwist(nextConfig);
