import { Geist, Geist_Mono, Newsreader } from "next/font/google";

// The ₹ glyph lives in latin-ext, so that subset is loaded for every family.
const display = Newsreader({
  subsets: ["latin", "latin-ext"],
  axes: ["opsz"],
  variable: "--font-newsreader",
  display: "swap",
});

const sans = Geist({ subsets: ["latin", "latin-ext"], variable: "--font-geist", display: "swap" });

const mono = Geist_Mono({ subsets: ["latin", "latin-ext"], variable: "--font-geist-mono", display: "swap" });

export const fontVariables = `${display.variable} ${sans.variable} ${mono.variable}`;
