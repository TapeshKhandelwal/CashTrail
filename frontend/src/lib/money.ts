/**
 * Exact money arithmetic. The API sends amounts as decimal strings ("48500.00");
 * all client-side maths happens in integer paise (BigInt) and goes back to a string.
 * Never convert an amount to `Number` to add, subtract or compare it.
 */

export type MoneyString = string;

export const ZERO: MoneyString = "0.00";

const MONEY_PATTERN = /^-?\d+(\.\d{1,2})?$/;
/** What a person may type into an amount field: digits, optional 1-2 decimals. */
export const MONEY_INPUT_PATTERN = /^\d+(\.\d{1,2})?$/;

export function isMoney(value: string): boolean {
  return MONEY_PATTERN.test(value.trim());
}

export function toPaise(value: MoneyString): bigint {
  const text = value.trim();
  if (!MONEY_PATTERN.test(text)) {
    throw new RangeError(`Not a money amount: "${value}"`);
  }
  const negative = text.startsWith("-");
  const [rupees, fraction = ""] = text.replace("-", "").split(".");
  const paise = BigInt(rupees) * 100n + BigInt(fraction.padEnd(2, "0"));
  return negative ? -paise : paise;
}

export function fromPaise(paise: bigint): MoneyString {
  const negative = paise < 0n;
  const abs = negative ? -paise : paise;
  const rupees = abs / 100n;
  const fraction = (abs % 100n).toString().padStart(2, "0");
  return `${negative ? "-" : ""}${rupees}.${fraction}`;
}

/** Canonical two-place form, e.g. "1500" -> "1500.00". */
export function normalizeMoney(value: MoneyString): MoneyString {
  return fromPaise(toPaise(value));
}

export function sumMoney(values: Iterable<MoneyString>): MoneyString {
  let total = 0n;
  for (const value of values) total += toPaise(value);
  return fromPaise(total);
}

export function addMoney(...values: MoneyString[]): MoneyString {
  return sumMoney(values);
}

export function subMoney(a: MoneyString, b: MoneyString): MoneyString {
  return fromPaise(toPaise(a) - toPaise(b));
}

/** Amount × whole count, e.g. a ₹500 note × 61. */
export function mulMoney(value: MoneyString, count: number | bigint): MoneyString {
  const times = typeof count === "bigint" ? count : BigInt(Math.trunc(count));
  return fromPaise(toPaise(value) * times);
}

export function compareMoney(a: MoneyString, b: MoneyString): -1 | 0 | 1 {
  const diff = toPaise(a) - toPaise(b);
  return diff === 0n ? 0 : diff < 0n ? -1 : 1;
}

export const isZero = (value: MoneyString) => toPaise(value) === 0n;
export const isNegative = (value: MoneyString) => toPaise(value) < 0n;
export const isPositive = (value: MoneyString) => toPaise(value) > 0n;
export const absMoney = (value: MoneyString) => value.trim().replace(/^-/, "");
export const negateMoney = (value: MoneyString) => fromPaise(-toPaise(value));

/** Ratio for progress bars and meters only (never for money results). Clamped to [0, 1]. */
export function moneyRatio(part: MoneyString, whole: MoneyString): number {
  const denominator = toPaise(whole);
  if (denominator <= 0n) return 0;
  const basisPoints = (toPaise(part) * 10_000n) / denominator;
  return Math.min(1, Math.max(0, Number(basisPoints) / 10_000));
}

/**
 * Turns typed input ("12,450", " 2450.5 ") into a canonical amount, or `null` when it is not
 * a valid positive-or-zero amount with at most two decimals.
 */
export function parseMoneyInput(raw: string): MoneyString | null {
  const text = raw.replace(/[,\s₹]/g, "");
  if (!MONEY_INPUT_PATTERN.test(text)) return null;
  return normalizeMoney(text);
}
