"use client";

import { RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

export function RetryButton() {
  return (
    <Button size="lg" onClick={() => window.location.reload()}>
      <RotateCcw data-icon="inline-start" />
      Try again
    </Button>
  );
}
