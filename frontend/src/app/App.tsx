import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { queryClient } from "@/shared/api/queryClient";
import { router } from "@/app/router";
import { ToastContainer } from "@/shared/components/Toast";
import { useAuthInit } from "@/features/auth/hooks";

function AuthInitializer() {
  useAuthInit();
  return null;
}

export function App() {
  return (
    <>
      <QueryClientProvider client={queryClient}>
        <AuthInitializer />
        <RouterProvider router={router} />
      </QueryClientProvider>
      <ToastContainer />
    </>
  );
}
