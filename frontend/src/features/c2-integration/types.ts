export interface C2Framework {
  id: string;
  name: string;
  type: "commercial" | "open_source";
  status: "connected" | "disconnected" | "not_configured";
  description: string;
  supported_protocols: string[];
  documentation_url: string;
}
