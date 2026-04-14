import { createBrowserRouter } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Layout } from "@/shared/components/Layout";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

const LoginPage = lazy(() =>
  import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })),
);
const RegisterPage = lazy(() =>
  import("@/features/auth/RegisterPage").then((m) => ({
    default: m.RegisterPage,
  })),
);
const InvestigationsPage = lazy(() =>
  import("@/features/investigations/InvestigationsPage").then((m) => ({
    default: m.InvestigationsPage,
  })),
);
const InvestigationDetailPage = lazy(() =>
  import("@/features/investigations/InvestigationDetailPage").then((m) => ({
    default: m.InvestigationDetailPage,
  })),
);
const GraphPage = lazy(() =>
  import("@/features/graph/GraphPage").then((m) => ({
    default: m.GraphPage,
  })),
);
const SettingsPage = lazy(() =>
  import("@/features/settings/SettingsPage").then((m) => ({
    default: m.SettingsPage,
  })),
);
const PaymentsPage = lazy(() =>
  import("@/features/payments/PaymentsPage").then((m) => ({
    default: m.PaymentsPage,
  })),
);

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingSpinner />}>{children}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <SuspenseWrapper>
        <LoginPage />
      </SuspenseWrapper>
    ),
  },
  {
    path: "/register",
    element: (
      <SuspenseWrapper>
        <RegisterPage />
      </SuspenseWrapper>
    ),
  },
  {
    path: "/",
    element: <Layout />,
    children: [
      {
        index: true,
        element: (
          <SuspenseWrapper>
            <InvestigationsPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: "investigations",
        element: (
          <SuspenseWrapper>
            <InvestigationsPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: "investigations/:id",
        element: (
          <SuspenseWrapper>
            <InvestigationDetailPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: "graph/:id",
        element: (
          <SuspenseWrapper>
            <GraphPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: "settings",
        element: (
          <SuspenseWrapper>
            <SettingsPage />
          </SuspenseWrapper>
        ),
      },
      {
        path: "payments",
        element: (
          <SuspenseWrapper>
            <PaymentsPage />
          </SuspenseWrapper>
        ),
      },
    ],
  },
]);
