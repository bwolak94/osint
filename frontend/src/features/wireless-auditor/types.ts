export interface WifiInterface {
  name: string;
  mac: string | null;
  mode: string | null;
  state: string | null;
  supports_monitor: boolean;
}

export interface AccessPoint {
  bssid: string;
  ssid: string;
  channel: number | null;
  frequency: string | null;
  signal_dbm: number | null;
  encryption: string | null;
}

export interface WifiClient {
  mac: string;
  signal_dbm: number | null;
  bssid: string | null;
}

export interface ScanResult {
  interface: string;
  access_points: AccessPoint[];
  scan_time: string;
  note: string | null;
}

export interface ClientScanResult {
  interface: string;
  gateway_bssid: string;
  clients: WifiClient[];
  scan_time: string;
}

export interface DeauthRequest {
  interface: string;
  gateway_mac: string;
  target_mac: string;
  count: number;
  reason_code: number;
}

export interface DeauthResult {
  success: boolean;
  interface: string;
  gateway_mac: string;
  target_mac: string;
  packets_sent: number;
  message: string;
}

export interface HardwareStatus {
  platform: string;
  is_linux: boolean;
  has_root: boolean;
  available_interfaces: WifiInterface[];
  hardware_ready: boolean;
  requirements_met: string[];
  requirements_missing: string[];
}

export type InterfaceMode = "monitor" | "managed";
