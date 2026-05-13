import { useMutation } from "@tanstack/react-query";
import { pivotEmail } from "./api";

export function useEmailPivot() {
  return useMutation({
    mutationFn: ({ email, hibpKey }: { email: string; hibpKey?: string }) =>
      pivotEmail(email, hibpKey ?? ""),
  });
}
