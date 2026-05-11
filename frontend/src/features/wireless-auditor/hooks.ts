import { useMutation, useQuery } from "@tanstack/react-query";
import { wirelessAuditorApi } from "./api";
import type { DeauthRequest, InterfaceMode } from "./types";

export const useHardwareStatus = () =>
  useQuery({
    queryKey: ["wireless-auditor", "status"],
    queryFn: wirelessAuditorApi.getStatus,
    refetchInterval: 30_000,
  });

export const useWifiInterfaces = () =>
  useQuery({
    queryKey: ["wireless-auditor", "interfaces"],
    queryFn: wirelessAuditorApi.listInterfaces,
  });

export const useSetInterfaceMode = () =>
  useMutation({
    mutationFn: ({ name, mode }: { name: string; mode: InterfaceMode }) =>
      wirelessAuditorApi.setInterfaceMode(name, mode),
  });

export const useScanNetworks = () =>
  useMutation({
    mutationFn: (iface: string) => wirelessAuditorApi.scanNetworks(iface),
  });

export const useScanClients = () =>
  useMutation({
    mutationFn: ({
      iface,
      bssid,
      duration,
    }: {
      iface: string;
      bssid: string;
      duration: number;
    }) => wirelessAuditorApi.scanClients(iface, bssid, duration),
  });

export const useDeauth = () =>
  useMutation({
    mutationFn: (req: DeauthRequest) => wirelessAuditorApi.deauth(req),
  });
