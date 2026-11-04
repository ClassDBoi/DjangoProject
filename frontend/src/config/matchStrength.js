/**
 * How match strength is shown instead of raw similarity numbers.
 *
 * The API only returns matches at or above the run's cutoff (0.50). Matches at or
 * above STRONG_MATCH are labelled "Strong match", the rest "Possible match".
 *
 * Why 0.55: in the team's blind review of 75 matches (November 2026), 9 of the 20
 * matches at 0.55 or above were rated relevant (15 at least partly), against 1 of
 * the 20 between 0.50 and 0.55. Revisit this if the matching or the data change.
 *
 * The same boundary decides whether an evidence link reads "closely matches" or
 * "is related to".
 */
export const STRONG_MATCH = 0.55;

export function matchStrength(similarity) {
    return Number(similarity) >= STRONG_MATCH
        ? { key: "strong", label: "Strong match" }
        : { key: "possible", label: "Possible match" };
}

export function linkPhrase(similarity) {
    return Number(similarity) >= STRONG_MATCH ? "closely matches" : "is related to";
}
