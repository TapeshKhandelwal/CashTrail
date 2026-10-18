"use client";

import { useEffect, useRef } from "react";

/**
 * The hero's ground: faint ledger ruling with a margin line, under two slow washes of the
 * brand and "cash in the field" colours. A 2D canvas, painted only while the hero is on screen,
 * and drawn once (static) under reduced motion.
 */
export function LedgerField() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dark = () => document.documentElement.classList.contains("dark");
    let width = 0;
    let height = 0;
    let frame = 0;
    let running = false;

    const washes = [
      { x: 0.78, y: 0.28, r: 0.55, rgb: "20, 103, 79", speed: 0.00011, phase: 0 },
      { x: 0.18, y: 0.78, r: 0.45, rgb: "169, 100, 26", speed: 0.00008, phase: 2.4 },
    ];

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const draw = (time: number) => {
      ctx.clearRect(0, 0, width, height);
      const ink = dark() ? "236, 234, 228" : "18, 20, 23";

      for (const wash of washes) {
        const cx = wash.x * width + Math.sin(time * wash.speed + wash.phase) * width * 0.05;
        const cy = wash.y * height + Math.cos(time * wash.speed * 0.8 + wash.phase) * height * 0.06;
        const radius = wash.r * Math.max(width, height);
        const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
        gradient.addColorStop(0, `rgba(${wash.rgb}, ${dark() ? 0.16 : 0.09})`);
        gradient.addColorStop(1, `rgba(${wash.rgb}, 0)`);
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, width, height);
      }

      // Ruled lines, fading out towards the bottom of the hero.
      const step = 34;
      for (let y = step * 2; y < height; y += step) {
        ctx.strokeStyle = `rgba(${ink}, ${0.055 * (1 - y / height)})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, y + 0.5);
        ctx.lineTo(width, y + 0.5);
        ctx.stroke();
      }

      // The ledger's margin rule.
      const margin = Math.min(96, width * 0.08);
      ctx.strokeStyle = `rgba(179, 68, 58, ${dark() ? 0.22 : 0.16})`;
      ctx.beginPath();
      ctx.moveTo(margin + 0.5, 0);
      ctx.lineTo(margin + 0.5, height);
      ctx.stroke();

      if (running && !reduced) frame = requestAnimationFrame(draw);
    };

    resize();
    draw(0);

    const visibility = new IntersectionObserver(([entry]) => {
      const visible = entry?.isIntersecting ?? false;
      if (visible && !running && !reduced) {
        running = true;
        frame = requestAnimationFrame(draw);
      } else if (!visible && running) {
        running = false;
        cancelAnimationFrame(frame);
      }
    });
    visibility.observe(canvas);

    const sizing = new ResizeObserver(() => {
      resize();
      draw(performance.now());
    });
    sizing.observe(canvas);

    return () => {
      running = false;
      cancelAnimationFrame(frame);
      visibility.disconnect();
      sizing.disconnect();
    };
  }, []);

  return <canvas ref={ref} aria-hidden className="pointer-events-none absolute inset-0 size-full" />;
}
