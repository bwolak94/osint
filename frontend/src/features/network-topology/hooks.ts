import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import type { NetworkTopologyResult } from "./types";

export function useNetworkDiscover() {
  return useMutation({
    mutationFn: async ({ network, depth = 2 }: { network: string; depth?: number }) => {
      const res = await apiClient.get<NetworkTopologyResult>("/network-topology/discover", {
        params: { network, depth },
      });
      return res.data;
    },
  });
}
