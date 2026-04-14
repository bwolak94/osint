import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/shared/api/queryClient";

interface ProvidersProps {
  children: React.ReactNode;
}

/**
 * Providers wrapper that sets up QueryClient and optional auth context.
 * Used as an alternative composition point if not using RouterProvider directly.
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
