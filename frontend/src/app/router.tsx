import { createBrowserRouter } from "react-router-dom";
import { lazy } from "react";
import { Layout } from "@/shared/components/Layout";
import { NotFoundPage } from "@/shared/components/NotFoundPage";
import { Lazy } from "./Lazy";
import { osintRoutes } from "./routes/osintRoutes";
import { pentestRoutes } from "./routes/pentestRoutes";

// Auth pages (no layout)
const LoginPage = lazy(() => import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import("@/features/auth/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const ForgotPasswordPage = lazy(() => import("@/features/auth/ForgotPasswordPage").then((m) => ({ default: m.ForgotPasswordPage })));

// Core layout pages
const DashboardPage = lazy(() => import("@/features/investigations/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const PaymentsPage = lazy(() => import("@/features/payments/PaymentsPage").then((m) => ({ default: m.PaymentsPage })));
const AdminPage = lazy(() => import("@/features/admin/AdminPage").then((m) => ({ default: m.AdminPage })));
const HubPage = lazy(() => import("@/features/hub").then((m) => ({ default: m.HubPage })));
const GdprPage = lazy(() => import("@/features/gdpr").then((m) => ({ default: m.GdprPage })));

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <Lazy name="Login"><LoginPage /></Lazy>,
  },
  {
    path: "/register",
    element: <Lazy name="Register"><RegisterPage /></Lazy>,
  },
  {
    path: "/forgot-password",
    element: <Lazy name="Forgot Password"><ForgotPasswordPage /></Lazy>,
  },
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Lazy name="Dashboard"><DashboardPage /></Lazy> },
      { path: "dashboard", element: <Lazy name="Dashboard"><DashboardPage /></Lazy> },
      { path: "settings", element: <Lazy name="Settings"><SettingsPage /></Lazy> },
      { path: "billing", element: <Lazy name="Billing"><PaymentsPage /></Lazy> },
      { path: "admin", element: <Lazy name="Admin"><AdminPage /></Lazy> },
      { path: "hub", element: <Lazy name="AI Hub"><HubPage /></Lazy> },
      { path: "gdpr", element: <Lazy name="GDPR"><GdprPage /></Lazy> },
      // OSINT feature routes
      ...osintRoutes,
      // Pentest feature routes
      ...pentestRoutes,
      // 404 catch-all for unmatched paths within the layout
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  // 404 for completely unmatched top-level paths
  { path: "*", element: <NotFoundPage /> },
]);
