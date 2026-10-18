import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

// Landing-only code: keep it out of the app shell and shared components (bundle budget).
const LANDING_ONLY = ["lenis", "lenis/*", "@/components/landing/*"];

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      "no-console": ["error", { allow: ["warn", "error"] }],
      "@typescript-eslint/no-explicit-any": "error",
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "framer-motion", message: "Import from motion/react; framer-motion ships inside motion." },
            { name: "vaul", message: "Use components/sheets (Base UI Drawer)." },
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/app/app/**",
      "src/app/(auth)/**",
      "src/components/{ui,layout,data-table,money,kpi,charts,status,feedback,sheets,receipt,auth,brand,pwa,agent,branch,finance,admin,dashboard}/**",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [
            { name: "framer-motion", message: "Import from motion/react; framer-motion ships inside motion." },
            { name: "vaul", message: "Use components/sheets (Base UI Drawer)." },
            {
              name: "motion/react",
              importNames: ["motion"],
              message: "App code renders inside <LazyMotion strict>; use `m` instead of `motion`.",
            },
          ],
          patterns: [{ group: LANDING_ONLY, message: "Landing-only dependency; keep it out of app bundles." }],
        },
      ],
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "src/types/api.d.ts", "public/**"]),
]);

export default eslintConfig;
