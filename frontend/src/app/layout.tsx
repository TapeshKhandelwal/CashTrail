import { SerwistProvider } from "@serwist/turbopack/react";
import type { Metadata, Viewport } from "next";

import { Providers } from "@/components/providers/providers";
import { SwUpdateToast } from "@/components/pwa/sw-update-toast";
import { IOS_SPLASH_SCREENS } from "@/lib/splash";

import { fontVariables } from "./fonts";
import "./globals.css";

const DESCRIPTION =
  "CashTrail follows every loan repayment, cash or UPI, from the customer's doorstep to the company's bank account.";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000"),
  applicationName: "CashTrail",
  title: { default: "CashTrail — Collections & Reconciliation", template: "%s · CashTrail" },
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: "CashTrail",
    title: "CashTrail — Every rupee collected, every rupee accounted for",
    description: DESCRIPTION,
    locale: "en_IN",
  },
  twitter: { card: "summary_large_image" },
  appleWebApp: {
    capable: true,
    title: "CashTrail",
    statusBarStyle: "default",
    startupImage: IOS_SPLASH_SCREENS,
  },
  formatDetection: { telephone: false, email: false, address: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FBFAF7" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1012" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-IN" className={fontVariables} suppressHydrationWarning>
      <body className="min-h-dvh bg-background font-sans text-foreground antialiased">
        <SerwistProvider
          swUrl="/serwist/sw.js"
          disable={process.env.NODE_ENV === "development"}
          cacheOnNavigation={false}
          reloadOnOnline={false}
          options={{ type: "classic", updateViaCache: "none" }}
        >
          <Providers>
            {children}
            <SwUpdateToast />
          </Providers>
        </SerwistProvider>
      </body>
    </html>
  );
}
