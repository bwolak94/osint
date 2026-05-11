import apiClient from "@/shared/api/client";
import type {
  AccessPoint,
  ClientScanResult,
  DeauthRequest,
  DeauthResult,
  HardwareStatus,
  InterfaceMode,
  ScanResult,
  WifiInterface,
} from "./types";

const BASE = "/api/v1/wireless-auditor";

export const wirelessAuditorApi = {
  getStatus: (): Promise<HardwareStatus> =>
    apiClient.get(`${BASE}/status`).then((r) => r.data),

  listInterfaces: (): Promise<WifiInterface[]> =>
    apiClient.get(`${BASE}/interfaces`).then((r) => r.data),

  setInterfaceMode: (interface_name: string, mode: InterfaceMode) =>
    apiClient
      .post(`${BASE}/interfaces/mode`, { interface: interface_name, mode })
      .then((r) => r.data),

  scanNetworks: (interface_name: string): Promise<ScanResult> =>
    apiClient
      .post(`${BASE}/scan/networks`, null, { params: { interface: interface_name } })
      .then((r) => r.data),

  scanClients: (
    interface_name: string,
    gateway_bssid: string,
    duration_s = 10
  ): Promise<ClientScanResult> =>
    apiClient
      .post(`${BASE}/scan/clients`, null, {
        params: { interface: interface_name, gateway_bssid, duration_s },
      })
      .then((r) => r.data),

  deauth: (req: DeauthRequest): Promise<DeauthResult> =>
    apiClient.post(`${BASE}/deauth`, req).then((r) => r.data),
};
