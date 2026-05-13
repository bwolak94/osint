import { useMutation } from "@tanstack/react-query";
import { searchPastes } from "./api";

export function usePasteMonitor() {
  return useMutation({ mutationFn: (query: string) => searchPastes(query) });
}
