"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { ThemeProvider } from "next-themes";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import type { ReactNode } from "react";

import { ThemeColorSync } from "@/components/pwa/theme-color-sync";
import { AppToaster } from "@/components/feedback/app-toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { getQueryClient } from "@/lib/api/query-client";

export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <NuqsAdapter>
          <TooltipProvider delayDuration={300}>
            {children}
            <AppToaster />
            <ThemeColorSync />
          </TooltipProvider>
        </NuqsAdapter>
        {process.env.NODE_ENV === "development" && (
          <ReactQueryDevtools buttonPosition="bottom-left" initialIsOpen={false} />
        )}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
