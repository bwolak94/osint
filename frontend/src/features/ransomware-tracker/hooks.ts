import { useMutation } from "@tanstack/react-query";
import { searchRansomware } from "./api";

export function useRansomwareTracker() {
  return useMutation({ mutationFn: (query: string) => searchRansomware(query) });
}
