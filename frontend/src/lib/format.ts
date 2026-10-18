import { absMoney, isNegative, toPaise, type MoneyString } from "@/lib/money";

const LOCALE = "en-IN";

const inr = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "INR" });
const inrWhole = new Intl.NumberFormat(LOCALE, {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});
const count = new Intl.NumberFormat(LOCALE);

// Intl formats numeric strings exactly (no float conversion), which keeps paise intact.
export type NumericString = `${number}`;
/** Money string typed for Intl / NumberFlow, which accept exact decimal strings. */
export const asNumeric = (value: MoneyString) => value.trim() as NumericString;

const amount = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Grouped amount without the symbol, for inputs: "12450.5" -> "12,450.50". */
export function formatAmount(value: MoneyString): string {
  return amount.format(asNumeric(value));
}

export interface FormatINROptions {
  /** Drop ".00" style paise (rounds half-even to rupees). Use for KPIs and charts, never receipts. */
  whole?: boolean;
  /** Prefix positive values with "+". */
  signed?: boolean;
}

/** `formatINR("123456.5")` -> "₹1,23,456.50". */
export function formatINR(value: MoneyString, { whole = false, signed = false }: FormatINROptions = {}) {
  const formatted = (whole ? inrWhole : inr).format(asNumeric(value));
  return signed && !isNegative(value) && toPaise(value) !== 0n ? `+${formatted}` : formatted;
}

const COMPACT_STEPS = [
  { paise: 10_000_000_00n, suffix: "Cr" },
  { paise: 100_000_00n, suffix: "L" },
  { paise: 1_000_00n, suffix: "K" },
] as const;

/** Compact Indian units for charts and tight KPI spots: "₹4.8L", "₹1.2Cr", "₹950". */
export function formatINRCompact(value: MoneyString): string {
  const paise = toPaise(value);
  const sign = paise < 0n ? "-" : "";
  const abs = paise < 0n ? -paise : paise;
  for (const { paise: unit, suffix } of COMPACT_STEPS) {
    if (abs >= unit) {
      const tenths = (abs * 10n + unit / 2n) / unit;
      const text = tenths % 10n === 0n ? `${tenths / 10n}` : `${tenths / 10n}.${tenths % 10n}`;
      return `${sign}₹${text}${suffix}`;
    }
  }
  return `${sign}${inrWhole.format(asNumeric(absMoney(value)))}`;
}

export function formatCount(value: number): string {
  return count.format(value);
}

/** API percentages arrive as strings ("93.50"). */
export function formatPercent(value: string | null | undefined, fractionDigits = 1): string {
  if (value == null) return "—";
  return `${new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: fractionDigits,
  }).format(value.trim() as NumericString)}%`;
}

/** Masks all but the last four characters: "XXXX4821" stays, "9876543210" -> "••••••3210". */
export function maskTail(value: string, visible = 4): string {
  if (value.length <= visible) return value;
  return `${"•".repeat(Math.min(6, value.length - visible))}${value.slice(-visible)}`;
}

const ONES = [
  "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
  "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];

function belowHundred(n: number): string {
  if (n < 20) return ONES[n];
  return [TENS[Math.floor(n / 10)], ONES[n % 10]].filter(Boolean).join(" ");
}

function belowThousand(n: number): string {
  const hundreds = Math.floor(n / 100);
  const rest = n % 100;
  return [hundreds ? `${ONES[hundreds]} Hundred` : "", rest ? belowHundred(rest) : ""]
    .filter(Boolean)
    .join(" ");
}

// Indian grouping: crore (10^7), lakh (10^5), thousand (10^3), then hundreds.
const INDIAN_UNITS = [
  { size: 10_000_000n, name: "Crore" },
  { size: 100_000n, name: "Lakh" },
  { size: 1_000n, name: "Thousand" },
] as const;

function rupeesInWords(rupees: bigint): string {
  if (rupees === 0n) return "Zero";
  const parts: string[] = [];
  let rest = rupees;
  const crores = rest / INDIAN_UNITS[0].size;
  if (crores > 0n) {
    parts.push(`${rupeesInWords(crores)} Crore`);
    rest %= INDIAN_UNITS[0].size;
  }
  for (const { size, name } of INDIAN_UNITS.slice(1)) {
    const chunk = rest / size;
    if (chunk > 0n) parts.push(`${belowHundred(Number(chunk))} ${name}`);
    rest %= size;
  }
  if (rest > 0n) parts.push(belowThousand(Number(rest)));
  return parts.join(" ");
}

/** For receipts: "Rupees Twelve Thousand Four Hundred and Fifty Paise Only". */
export function amountInWords(value: MoneyString): string {
  const paise = toPaise(absMoney(value));
  const rupees = paise / 100n;
  const fraction = Number(paise % 100n);
  const words = `Rupees ${rupeesInWords(rupees)}`;
  return fraction ? `${words} and ${belowHundred(fraction)} Paise Only` : `${words} Only`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0] ?? "";
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "";
  return `${first}${last}`.toUpperCase();
}

/** "1 receipt", "12 receipts", with en-IN grouping. */
export function countOf(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatCount(count)} ${count === 1 ? singular : plural}`;
}
