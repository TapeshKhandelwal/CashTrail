import { createSerwistRoute } from "@serwist/turbopack";

// Bump NEXT_PUBLIC_APP_VERSION on every deploy so the offline page is re-precached.
const revision = process.env.NEXT_PUBLIC_APP_VERSION ?? "dev";

export const { dynamic, dynamicParams, revalidate, generateStaticParams, GET } = createSerwistRoute({
  swSrc: "src/app/sw.ts",
  useNativeEsbuild: true,
  globIgnores: ["public/landing/**", "public/screenshots/**", "public/splash/**"],
  // Keeps unusually large chunks out of the install-time precache.
  maximumFileSizeToCacheInBytes: 524_288,
  additionalPrecacheEntries: [{ url: "/~offline", revision }],
  esbuildOptions: {
    define: {
      "process.env.NEXT_PUBLIC_API_URL": JSON.stringify(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"),
    },
  },
});
