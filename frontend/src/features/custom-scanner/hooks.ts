import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/shared/api/client";
import { toast } from "@/shared/components/Toast";
import type { CustomScanner, CreateScannerInput, ScanResult } from "./types";

export function useCustomScanners() {
  return useQuery({
    queryKey: ["custom-scanners"],
    queryFn: async () => {
      const res = await apiClient.get<CustomScanner[]>("/custom-scanner/scanners");
      return res.data;
    },
  });
}

export function useCreateScanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: CreateScannerInput) => {
      const res = await apiClient.post<CustomScanner>("/custom-scanner/scanners", data);
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-scanners"] });
      toast.success("Scanner created");
    },
    onError: () => toast.error("Failed to create scanner"),
  });
}

export function useAddStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ scannerId, stepType, outputKey }: { scannerId: string; stepType: string; outputKey: string }) => {
      const res = await apiClient.post<CustomScanner>(
        `/custom-scanner/scanners/${scannerId}/steps?step_type=${encodeURIComponent(stepType)}&output_key=${encodeURIComponent(outputKey)}`
      );
      return res.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["custom-scanners"] });
      toast.success("Step added");
    },
  });
}

export function useRunScanner() {
  return useMutation({
    mutationFn: async ({ scannerId, inputValue }: { scannerId: string; inputValue: string }) => {
      const res = await apiClient.post<ScanResult>(
        `/custom-scanner/scanners/${scannerId}/run?input_value=${encodeURIComponent(inputValue)}`
      );
      return res.data;
    },
    onSuccess: () => toast.success("Scan completed"),
    onError: () => toast.error("Scan failed"),
  });
}
