/**
 * MSW Node server for Vitest.
 * Import this in your test setup file:
 *   import { server } from "@/mocks/server";
 *   beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
 *   afterEach(() => server.resetHandlers());
 *   afterAll(() => server.close());
 */

import { setupServer } from "msw/node";
import { newFeatureHandlers } from "./handlers/investigationHandlers";

export const server = setupServer(...newFeatureHandlers);
