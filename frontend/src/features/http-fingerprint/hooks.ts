import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteHttpFingerprintScan, fingerprintUrl, listHttpFingerprintScans } from "./api";

export function useHttpFingerprint() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => fingerprintUrl(url),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["http-fingerprint-history"] }),
  });
}

export function useHttpFingerprintHistory(page = 1, page_size = 20) {
  return useQuery({
    queryKey: ["http-fingerprint-history", page, page_size],
    queryFn: () => listHttpFingerprintScans(page, page_size),
  });
}

export function useDeleteHttpFingerprintScan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteHttpFingerprintScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["http-fingerprint-history"] }),
  });
}
