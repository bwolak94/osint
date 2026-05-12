import apiClient from "@/shared/api/client";
import type { HarvestRequest, HarvestResult } from "./types";

const BASE = "/domain-intel";

export const domainIntelApi = {
  harvest: (req: HarvestRequest): Promise<HarvestResult> =>
    apiClient.post(`${BASE}/harvest`, req).then((r) => r.data),

  listSources: (): Promise<{ sources: string[] }> =>
    apiClient.get(`${BASE}/sources`).then((r) => r.data),
};
