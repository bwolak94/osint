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
const PlaybooksPage = lazy(() => import("@/features/playbooks/PlaybooksPage").then((m) => ({ default: m.PlaybooksPage })));
const ImageCheckerPage = lazy(() => import("@/features/image-checker").then((m) => ({ default: m.ImageCheckerPage })));
const DocMetadataPage = lazy(() => import("@/features/doc-metadata").then((m) => ({ default: m.DocMetadataPage })));
const EmailHeadersPage = lazy(() => import("@/features/email-headers").then((m) => ({ default: m.EmailHeadersPage })));
const MacLookupPage = lazy(() => import("@/features/mac-lookup").then((m) => ({ default: m.MacLookupPage })));
const DomainPermutationPage = lazy(() => import("@/features/domain-permutation").then((m) => ({ default: m.DomainPermutationPage })));
const CloudExposurePage = lazy(() => import("@/features/cloud-exposure").then((m) => ({ default: m.CloudExposurePage })));
const StealerLogsPage = lazy(() => import("@/features/stealer-logs").then((m) => ({ default: m.StealerLogsPage })));
const SupplyChainPage = lazy(() => import("@/features/supply-chain").then((m) => ({ default: m.SupplyChainPage })));
const FediversePage = lazy(() => import("@/features/fediverse").then((m) => ({ default: m.FediversePage })));
const WiglePage = lazy(() => import("@/features/wigle").then((m) => ({ default: m.WiglePage })));

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
      { path: "playbooks", element: <Lazy><PlaybooksPage /></Lazy> },
      { path: "admin", element: <Lazy><AdminPage /></Lazy> },
      { path: "settings", element: <Lazy><SettingsPage /></Lazy> },
      { path: "billing", element: <Lazy><PaymentsPage /></Lazy> },
      { path: "image-checker", element: <Lazy><ImageCheckerPage /></Lazy> },
      { path: "doc-metadata", element: <Lazy><DocMetadataPage /></Lazy> },
      { path: "email-headers", element: <Lazy><EmailHeadersPage /></Lazy> },
      { path: "mac-lookup", element: <Lazy><MacLookupPage /></Lazy> },
      { path: "domain-permutation", element: <Lazy><DomainPermutationPage /></Lazy> },
      { path: "cloud-exposure", element: <Lazy><CloudExposurePage /></Lazy> },
      { path: "stealer-logs", element: <Lazy><StealerLogsPage /></Lazy> },
      { path: "supply-chain", element: <Lazy><SupplyChainPage /></Lazy> },
      { path: "fediverse", element: <Lazy><FediversePage /></Lazy> },
      { path: "wigle", element: <Lazy><WiglePage /></Lazy> },
    ],
  },
]);
