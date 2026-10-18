import { fromPaise, toPaise, type MoneyString } from "@/lib/money";
import type { DenominationKey, Denominations } from "@/types/domain";

/** Notes and coins counted at hand-over. ₹2000 is withdrawn from circulation, so it is opt-in. */
export const DEFAULT_DENOMINATIONS: DenominationKey[] = ["500", "200", "100", "50", "20", "10", "5", "2", "1"];
export const ALL_DENOMINATIONS: DenominationKey[] = ["2000", ...DEFAULT_DENOMINATIONS];

export const isCoin = (key: DenominationKey) => Number(key) < 10;

export function lineTotal(key: DenominationKey, count: number): MoneyString {
  return fromPaise(BigInt(key) * 100n * BigInt(Math.max(0, Math.trunc(count))));
}

/** Exact total of a count, in paise arithmetic. */
export function denominationsTotal(counts: Denominations): MoneyString {
  let paise = 0n;
  for (const [key, count] of Object.entries(counts) as [DenominationKey, number | undefined][]) {
    if (count) paise += BigInt(key) * 100n * BigInt(Math.trunc(count));
  }
  return fromPaise(paise);
}

/** Drops zero rows so the payload matches what the API stores. */
export function compactDenominations(counts: Denominations): Denominations {
  return Object.fromEntries(Object.entries(counts).filter(([, count]) => (count ?? 0) > 0)) as Denominations;
}

/**
 * Largest-first split of a whole-rupee amount ("Fill from declared"). Any paise or a remainder
 * the available denominations can't make are left uncounted for the person to resolve.
 */
export function fillDenominations(amount: MoneyString, keys: DenominationKey[] = DEFAULT_DENOMINATIONS): Denominations {
  let rupees = toPaise(amount) / 100n;
  const result: Denominations = {};
  for (const key of [...keys].sort((a, b) => Number(b) - Number(a))) {
    const value = BigInt(key);
    const count = rupees / value;
    if (count > 0n) {
      result[key] = Number(count);
      rupees -= count * value;
    }
  }
  return result;
}
