import { createBrowserRouter } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Layout } from "@/shared/components/Layout";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";

const LoginPage = lazy(() => import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/features/auth/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const ForgotPasswordPage = lazy(() => import("@/features/auth/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })));
const DashboardPage = lazy(() => import("@/features/investigations/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const InvestigationsPage = lazy(() => import("@/features/investigations/InvestigationsPage").then((m) => ({ default: m.InvestigationsPage })));
const InvestigationDetailPage = lazy(() => import("@/features/investigations/InvestigationDetailPage").then((m) => ({ default: m.InvestigationDetailPage })));
const GraphPage = lazy(() => import("@/features/graph/GraphPage").then((m) => ({ default: m.GraphPage })));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const PaymentsPage = lazy(() => import("@/features/payments/PaymentsPage").then((m) => ({ default: m.PaymentsPage })));
const ScannersPage = lazy(() => import("@/features/scanners/ScannersPage").then((m) => ({ default: m.ScannersPage })));
const AdminPage = lazy(() => import("@/features/admin/AdminPage").then((m) => ({ default: m.AdminPage })));

function Lazy({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<LoadingSpinner size="lg" className="mt-32" />}>
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <Lazy><LoginPage /></Lazy>,
  },
  {
    path: "/register",
    element: <Lazy><RegisterPage /></Lazy>,
  },
  {
    path: "/forgot-password",
    element: <Lazy><ForgotPasswordPage /></Lazy>,
  },
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Lazy><DashboardPage /></Lazy> },
      { path: "dashboard", element: <Lazy><DashboardPage /></Lazy> },
      { path: "investigations", element: <Lazy><InvestigationsPage /></Lazy> },
      { path: "investigations/:id", element: <Lazy><InvestigationDetailPage /></Lazy> },
      { path: "investigations/:id/graph", element: <Lazy><GraphPage /></Lazy> },
      { path: "scanners", element: <Lazy><ScannersPage /></Lazy> },
      { path: "admin", element: <Lazy><AdminPage /></Lazy> },
      { path: "settings", element: <Lazy><SettingsPage /></Lazy> },
      { path: "billing", element: <Lazy><PaymentsPage /></Lazy> },
    ],
  },
]);
