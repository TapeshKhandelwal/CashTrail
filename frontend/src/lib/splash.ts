/**
 * iOS launch screens (separate PNGs, not data URLs: WebKit bug 280262), on paper in light
 * mode and on night ink in dark mode. Files live in public/splash.
 */
const DEVICES = [
  { width: 430, height: 932, ratio: 3 },
  { width: 393, height: 852, ratio: 3 },
  { width: 428, height: 926, ratio: 3 },
  { width: 390, height: 844, ratio: 3 },
  { width: 375, height: 812, ratio: 3 },
  { width: 414, height: 896, ratio: 2 },
  { width: 375, height: 667, ratio: 2 },
  { width: 820, height: 1180, ratio: 2 },
  { width: 1024, height: 1366, ratio: 2 },
] as const;

const SCHEMES = [
  { suffix: "", scheme: "light" },
  { suffix: "-dark", scheme: "dark" },
] as const;

export const IOS_SPLASH_SCREENS = DEVICES.flatMap(({ width, height, ratio }) =>
  SCHEMES.map(({ suffix, scheme }) => ({
    url: `/splash/apple-splash-${width * ratio}x${height * ratio}${suffix}.png`,
    media: `(device-width: ${width}px) and (device-height: ${height}px) and (-webkit-device-pixel-ratio: ${ratio}) and (orientation: portrait) and (prefers-color-scheme: ${scheme})`,
  })),
);
