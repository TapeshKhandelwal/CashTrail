"use client";

import { Share, SquarePlus, ToggleRight } from "lucide-react";
import { AnimatePresence, m } from "motion/react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { LogoMark } from "@/components/brand/logo-mark";
import { BottomSheet } from "@/components/sheets/bottom-sheet";
import { Button } from "@/components/ui/button";
import {
  getPlatform,
  INSTALL_EVENT,
  isInstallEligible,
  promptInstall,
  snoozeInstallPrompt,
  useInstallPromptEvent,
  useIsStandalone,
  type Platform,
} from "@/lib/pwa";
import { transition } from "@/lib/motion";

const IOS_STEPS = [
  { icon: Share, text: "Tap Share in Safari's toolbar (on iOS 26 compact tabs, tap ••• first)." },
  { icon: SquarePlus, text: "Choose Add to Home Screen." },
  { icon: ToggleRight, text: "Keep “Open as Web App” on, then tap Add." },
];

/**
 * Install card above the tab bar: native prompt on Android/desktop Chrome, a how-to sheet on
 * iOS. Shows only after a meaningful moment or a second session, never when installed, and
 * "Not now" snoozes it for 14 days. `requestInstallPrompt()` opens it on demand.
 */
export function InstallPrompt() {
  const standalone = useIsStandalone();
  const nativePrompt = useInstallPromptEvent();
  const [platform, setPlatform] = useState<Platform | null>(null);
  const [visible, setVisible] = useState(false);
  const [howToOpen, setHowToOpen] = useState(false);

  useEffect(() => {
    // Platform and storage only exist in the browser; read them once after mount.
    const detected = getPlatform();
    const eligible = isInstallEligible();
    const timer = setTimeout(() => {
      setPlatform(detected);
      setVisible(eligible);
    }, 0);
    const show = () => setVisible(true);
    const onEligible = () => setVisible(isInstallEligible());
    const onInstalled = () => {
      setVisible(false);
      toast.success("CashTrail installed. Find it on your home screen.");
    };
    window.addEventListener(INSTALL_EVENT, show);
    window.addEventListener(`${INSTALL_EVENT}:eligible`, onEligible);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      clearTimeout(timer);
      window.removeEventListener(INSTALL_EVENT, show);
      window.removeEventListener(`${INSTALL_EVENT}:eligible`, onEligible);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const canInstall = Boolean(nativePrompt) || platform === "ios";
  const open = visible && !standalone && canInstall;

  const install = async () => {
    if (nativePrompt) {
      const outcome = await promptInstall();
      if (outcome !== "accepted") snoozeInstallPrompt();
      setVisible(false);
    } else {
      setHowToOpen(true);
    }
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <m.aside
            aria-label="Install CashTrail"
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 24, opacity: 0 }}
            transition={transition.sheet}
            className="fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+5rem)] z-50 flex flex-col gap-3.5 rounded-xl border border-rule bg-raised p-4 shadow-float md:right-6 md:bottom-6 md:left-auto md:w-96"
          >
            <div className="flex items-start gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-rule bg-paper">
                <LogoMark className="size-6" />
              </span>
              <div className="flex flex-col gap-0.5">
                <p className="text-[14.5px] font-medium text-ink">Install CashTrail</p>
                <p className="text-[13px] text-dim">Open it from your home screen, full-screen and faster.</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={install}>
                {nativePrompt ? "Install" : "Show me how"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  snoozeInstallPrompt();
                  setVisible(false);
                }}
              >
                Not now
              </Button>
            </div>
          </m.aside>
        )}
      </AnimatePresence>

      <BottomSheet
        open={howToOpen}
        onOpenChange={setHowToOpen}
        title="Add CashTrail to your Home Screen"
        description="Safari installs web apps from the Share menu."
        footer={
          <Button size="xl" className="w-full" onClick={() => setHowToOpen(false)}>
            Got it
          </Button>
        }
      >
        <ol className="flex flex-col gap-3 pb-2">
          {IOS_STEPS.map((step, index) => (
            <li key={step.text} className="flex items-center gap-3 rounded-xl border border-rule p-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sunk text-ink">
                <step.icon className="size-5" aria-hidden />
              </span>
              <span className="text-[13.5px] text-ink">
                <span className="mr-1 font-mono text-[11px] text-faint">{index + 1}</span>
                {step.text}
              </span>
            </li>
          ))}
        </ol>
      </BottomSheet>
    </>
  );
}
