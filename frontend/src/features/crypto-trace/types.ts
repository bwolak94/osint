export interface CryptoTransaction {
  txid: string;
  block_height: number;
  timestamp: string;
  from_address: string;
  to_address: string;
  amount: number;
  currency: string;
  usd_value: number;
  is_mixer: boolean;
  is_exchange: boolean;
  risk_score: number;
  labels: string[];
}

export interface AddressInfo {
  address: string;
  currency: string;
  total_received: number;
  total_sent: number;
  balance: number;
  tx_count: number;
  first_seen: string;
  last_seen: string;
  risk_score: number;
  risk_level: string;
  labels: string[];
  cluster_size: number;
}

export interface CryptoTraceResult {
  address: string;
  address_info: AddressInfo;
  transactions: CryptoTransaction[];
  connected_addresses: Array<{ address: string; risk_score: number; labels: string[] }>;
  risk_indicators: string[];
}
