/**
 * Runtime response validation using Zod.
 *
 * TypeScript types only exist at compile time. Without runtime validation,
 * a backend schema change (e.g. a renamed field) silently produces `undefined`
 * values in the UI instead of a clear error. (#27)
 *
 * Usage:
 *
 *   import { z } from "zod";
 *   import { validateResponse } from "@/shared/api/validateResponse";
 *
 *   const InvestigationSchema = z.object({
 *     id: z.string().uuid(),
 *     title: z.string(),
 *     status: z.enum(["draft", "running", "completed", "paused", "archived"]),
 *   });
 *
 *   // In your api.ts:
 *   export async function getInvestigation(id: string) {
 *     const res = await apiClient.get(`/investigations/${id}`);
 *     return validateResponse(InvestigationSchema, res.data, "getInvestigation");
 *   }
 */

import { z } from "zod";

/**
 * Validate `data` against `schema` and return the parsed value.
 *
 * In development: throws a `ZodError` immediately so schema drift is caught
 * during development.
 *
 * In production: logs a warning and returns the raw data cast to `T` so the
 * app degrades gracefully rather than crashing on minor API drift.
 */
export function validateResponse<T>(
  schema: z.ZodType<T>,
  data: unknown,
  context: string,
): T {
  const result = schema.safeParse(data);

  if (result.success) {
    return result.data;
  }

  const issues = result.error.issues
    .map((i) => `${i.path.join(".")}: ${i.message}`)
    .join("; ");

  if (import.meta.env.DEV) {
    throw new Error(`[validateResponse] Schema mismatch in ${context}: ${issues}`);
  }

  console.warn(
    `[validateResponse] Schema mismatch in ${context} — returning raw data:`,
    issues,
  );

  // Return raw data in production so UI degrades gracefully
  return data as T;
}

/**
 * Create a typed API fetcher that validates the response at runtime.
 *
 * Example:
 *   export const fetchInvestigation = createValidatedFetcher(InvestigationSchema);
 *   const inv = await fetchInvestigation(rawResponse);
 */
export function createValidatedFetcher<T>(
  schema: z.ZodType<T>,
  context: string,
): (data: unknown) => T {
  return (data: unknown) => validateResponse(schema, data, context);
}
