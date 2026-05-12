/**
 * Shared TanStack Query configuration constants.
 *
 * Import these instead of using magic numbers so staleTime/gcTime are
 * consistent across the entire codebase and easy to tune in one place.
 */

/** Data that changes rarely — e.g. user profile, workspace settings. */
export const STALE_NEVER = Infinity;

/** 10 minutes — risk scores, pivot recommendations, scanner health. */
export const STALE_10M = 10 * 60 * 1000;

/** 5 minutes — investigation detail, scan results. */
export const STALE_5M = 5 * 60 * 1000;

/** 1 minute — investigation list, quota data. */
export const STALE_1M = 60 * 1000;

/** 30 seconds — real-time feeds, watchlist alerts. */
export const STALE_30S = 30 * 1000;

/** Re-fetch immediately on every mount — used for live/running investigations. */
export const STALE_0 = 0;

/** Default garbage-collection time: keep unused cache for 5 minutes. */
export const GC_5M = 5 * 60 * 1000;

/** GC time for large graph data — evict quickly to free memory. */
export const GC_1M = 60 * 1000;
