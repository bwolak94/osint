/**
 * Shared TanStack Query configuration constants.
 *
 * Import these instead of using magic numbers so staleTime/gcTime are
 * consistent across the entire codebase and easy to tune in one place.
 *
 * All duration constants are typed as `Milliseconds` — a branded number type
 * that prevents accidentally passing seconds where milliseconds are expected
 * (a common source of "why is my data always stale?" bugs). (#23)
 */

/** Branded type for millisecond durations. Prevents seconds/ms mix-ups. */
export type Milliseconds = number & { readonly __brand: "Milliseconds" };

const ms = (n: number): Milliseconds => n as Milliseconds;

/** Data that changes rarely — e.g. user profile, workspace settings. */
export const STALE_NEVER = Infinity as Milliseconds;

/** 10 minutes — risk scores, pivot recommendations, scanner health. */
export const STALE_10M = ms(10 * 60 * 1000);

/** 5 minutes — investigation detail, scan results. */
export const STALE_5M = ms(5 * 60 * 1000);

/** 1 minute — investigation list, quota data. */
export const STALE_1M = ms(60 * 1000);

/** 30 seconds — real-time feeds, watchlist alerts. */
export const STALE_30S = ms(30 * 1000);

/** Re-fetch immediately on every mount — used for live/running investigations. */
export const STALE_0 = ms(0);

/** Default garbage-collection time: keep unused cache for 5 minutes. */
export const GC_5M = ms(5 * 60 * 1000);

/** GC time for large graph data — evict quickly to free memory. */
export const GC_1M = ms(60 * 1000);
