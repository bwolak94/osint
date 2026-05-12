/**
 * MSW 2.x request handlers for investigation-related endpoints.
 * Import these in tests or the browser service worker setup.
 */

import { http, HttpResponse } from "msw";

const BASE = "/api/v1";

// ---------------------------------------------------------------------------
// Risk score
// ---------------------------------------------------------------------------
export const riskScoreHandlers = [
  http.get(`${BASE}/investigations/:id/risk-score`, ({ params }) => {
    return HttpResponse.json({
      investigation_id: params.id,
      score: 42,
      label: "medium",
      breach_count: 2,
      exposed_services: 5,
      avg_confidence: 0.78,
      factors: { breach: 20, exposed_services: 12, avg_confidence: 10 },
      computed_at: new Date().toISOString(),
    });
  }),
];

// ---------------------------------------------------------------------------
// Pivot recommendations
// ---------------------------------------------------------------------------
export const pivotRecommendationHandlers = [
  http.get(`${BASE}/investigations/:id/pivot-recommendations`, ({ params }) => {
    return HttpResponse.json({
      investigation_id: params.id,
      recommendations: [
        {
          scanner: "shodan_scanner",
          reason: "IP has open ports suggesting exposed services.",
          target: "1.2.3.4",
          confidence: "high",
        },
        {
          scanner: "hibp_scanner",
          reason: "Email found in multiple leaks.",
          target: "user@example.com",
          confidence: "medium",
        },
      ],
      summary: "Recommended pivoting via Shodan and HIBP for deeper exposure analysis.",
    });
  }),
];

// ---------------------------------------------------------------------------
// Scanner quota
// ---------------------------------------------------------------------------
export const scannerQuotaHandlers = [
  http.get(`${BASE}/scanner-quota`, () => {
    return HttpResponse.json({
      quotas: [
        {
          workspace_id: "ws-1",
          scanner_name: "shodan_scanner",
          monthly_limit: 1000,
          requests_used: 423,
          period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(),
          alerts_enabled: true,
        },
        {
          workspace_id: "ws-1",
          scanner_name: "hibp_scanner",
          monthly_limit: 500,
          requests_used: 499,
          period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(),
          alerts_enabled: true,
        },
      ],
      total_scanners: 2,
      over_limit: 0,
      near_limit: 1,
    });
  }),

  http.post(`${BASE}/scanner-quota`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json(
      {
        workspace_id: "ws-1",
        scanner_name: body.scanner_name,
        monthly_limit: body.monthly_limit,
        requests_used: 0,
        period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(),
        alerts_enabled: body.alerts_enabled ?? true,
      },
      { status: 200 },
    );
  }),
];

// ---------------------------------------------------------------------------
// STIX export
// ---------------------------------------------------------------------------
export const stixExportHandlers = [
  http.get(`${BASE}/investigations/:id/export/stix`, ({ params }) => {
    return HttpResponse.json({
      type: "bundle",
      id: `bundle--${params.id}`,
      spec_version: "2.1",
      objects: [],
    });
  }),
];

// ---------------------------------------------------------------------------
// Investigation ACL
// ---------------------------------------------------------------------------
export const investigationAclHandlers = [
  http.get(`${BASE}/investigations/:id/acl`, () => {
    return HttpResponse.json([]);
  }),
  http.post(`${BASE}/investigations/:id/acl`, async ({ params, request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json(
      {
        investigation_id: params.id,
        user_id: body.user_id,
        permission: body.permission,
        granted_by: "current-user-id",
        granted_at: new Date().toISOString(),
      },
      { status: 201 },
    );
  }),
  http.delete(`${BASE}/investigations/:id/acl/:userId`, () => {
    return new HttpResponse(null, { status: 204 });
  }),
];

// ---------------------------------------------------------------------------
// All new handlers combined
// ---------------------------------------------------------------------------
export const newFeatureHandlers = [
  ...riskScoreHandlers,
  ...pivotRecommendationHandlers,
  ...scannerQuotaHandlers,
  ...stixExportHandlers,
  ...investigationAclHandlers,
];
