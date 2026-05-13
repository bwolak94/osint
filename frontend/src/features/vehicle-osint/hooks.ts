import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { scanVehicleOsint, listVehicleOsintScans, deleteVehicleOsintScan } from "./api";

export const useScanVehicleOsint = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ query, query_type }: { query: string; query_type: string }) =>
      scanVehicleOsint(query, query_type),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vehicle-osint-history"] }),
  });
};

export const useVehicleOsintHistory = (page = 1, page_size = 20) =>
  useQuery({
    queryKey: ["vehicle-osint-history", page, page_size],
    queryFn: () => listVehicleOsintScans(page, page_size),
  });

export const useDeleteVehicleOsintScan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteVehicleOsintScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["vehicle-osint-history"] }),
  });
};
