import { useMutation } from "@tanstack/react-query";
import { scanUsername } from "./api";

export function useUsernameScanner() {
  return useMutation({ mutationFn: (username: string) => scanUsername(username) });
}
