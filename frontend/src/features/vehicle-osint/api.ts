import apiClient from "@/shared/api/client";
import type { VehicleOsintScan, VehicleOsintListResponse } from "./types";

export const scanVehicleOsint = (query: string, query_type: string): Promise<VehicleOsintScan> =>
  apiClient.post<VehicleOsintScan>("/vehicle-osint/", { query, query_type }).then((r) => r.data);

export const listVehicleOsintScans = (page = 1, page_size = 20): Promise<VehicleOsintListResponse> =>
  apiClient
    .get<VehicleOsintListResponse>("/vehicle-osint/", { params: { page, page_size } })
    .then((r) => r.data);

export const deleteVehicleOsintScan = (id: string): Promise<void> =>
  apiClient.delete(`/vehicle-osint/${id}`).then(() => undefined);
