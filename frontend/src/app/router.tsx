import { createBrowserRouter } from "react-router-dom";
import { lazy, Suspense } from "react";
import { Layout } from "@/shared/components/Layout";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";
import { FeatureErrorBoundary } from "@/shared/components/FeatureErrorBoundary";

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
const TechReconPage = lazy(() => import("@/features/tech-recon").then((m) => ({ default: m.TechReconPage })));
const SocmintPage = lazy(() => import("@/features/socmint").then((m) => ({ default: m.SocmintPage })));
const CredentialIntelPage = lazy(() => import("@/features/credential-intel").then((m) => ({ default: m.CredentialIntelPage })));
const ImintPage = lazy(() => import("@/features/imint").then((m) => ({ default: m.ImintPage })));
const EngagementsPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.EngagementsPage })));
const EngagementDetailPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.EngagementDetailPage })));
const NewScanPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.NewScanPage })));
const ScanDetailPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.ScanDetailPage })));
const FindingsPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.FindingsPage })));
const ReportPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.ReportPage })));
const AttackPlannerPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.AttackPlannerPage })));
const CompliancePage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.CompliancePage })));
const ExecutiveDashboardPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.ExecutiveDashboardPage })));
const BASPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.BASPage })));
const FindingLibraryPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.FindingLibraryPage })));
const AttackPlannerIndexPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.AttackPlannerIndexPage })));
const TargetsPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.TargetsPage })));
const TargetDashboardPage = lazy(() => import("@/features/pentesting").then((m) => ({ default: m.TargetDashboardPage })));
const HubPage = lazy(() => import("@/features/hub").then((m) => ({ default: m.HubPage })));
const WatchlistPage = lazy(() => import("@/features/watchlist/WatchlistPage").then((m) => ({ default: m.WatchlistPage })));
const ReportBuilderPage = lazy(() => import("@/features/report-builder/ReportBuilderPage").then((m) => ({ default: m.ReportBuilderPage })));
const InvestigationDiffPage = lazy(() => import("@/features/investigation-diff/InvestigationDiffPage").then((m) => ({ default: m.InvestigationDiffPage })));
const CampaignsPage = lazy(() => import("@/features/campaigns/CampaignsPage").then((m) => ({ default: m.CampaignsPage })));
const ThreatActorsPage = lazy(() => import("@/features/threat-actors/ThreatActorsPage").then((m) => ({ default: m.ThreatActorsPage })));
const GdprPage = lazy(() => import("@/features/gdpr").then((m) => ({ default: m.GdprPage })));
const MaltegoPage = lazy(() => import("@/features/maltego/MaltegoPage").then((m) => ({ default: m.MaltegoPage })));

function Lazy({ children, name }: { children: React.ReactNode; name?: string }) {
  return (
    <FeatureErrorBoundary featureName={name}>
      <Suspense fallback={<LoadingSpinner size="lg" className="mt-32" />}>
        {children}
      </Suspense>
    </FeatureErrorBoundary>
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
      { path: "tech-recon", element: <Lazy><TechReconPage /></Lazy> },
      { path: "socmint", element: <Lazy><SocmintPage /></Lazy> },
      { path: "credential-intel", element: <Lazy><CredentialIntelPage /></Lazy> },
      { path: "imint", element: <Lazy><ImintPage /></Lazy> },
      { path: "pentest/engagements", element: <Lazy><EngagementsPage /></Lazy> },
      { path: "pentest/engagements/:id", element: <Lazy><EngagementDetailPage /></Lazy> },
      { path: "pentest/engagements/:id/scan/new", element: <Lazy><NewScanPage /></Lazy> },
      { path: "pentest/scans/:id", element: <Lazy><ScanDetailPage /></Lazy> },
      { path: "pentest/scans/:id/planner", element: <Lazy><AttackPlannerPage /></Lazy> },
      { path: "pentest/findings", element: <Lazy><FindingsPage /></Lazy> },
      { path: "pentest/reports/:id", element: <Lazy><ReportPage /></Lazy> },
      { path: "pentest/compliance", element: <Lazy><CompliancePage /></Lazy> },
      { path: "pentest/dashboard", element: <Lazy><ExecutiveDashboardPage /></Lazy> },
      { path: "pentest/bas", element: <Lazy><BASPage /></Lazy> },
      { path: "pentest/finding-library", element: <Lazy><FindingLibraryPage /></Lazy> },
      { path: "pentest/attack-planner", element: <Lazy><AttackPlannerIndexPage /></Lazy> },
      { path: "pentest/targets", element: <Lazy><TargetsPage /></Lazy> },
      { path: "pentest/targets/:engagementId", element: <Lazy><TargetDashboardPage /></Lazy> },
      { path: "hub", element: <Lazy><HubPage /></Lazy> },
      { path: "watchlist", element: <Lazy><WatchlistPage /></Lazy> },
      { path: "report-builder", element: <Lazy><ReportBuilderPage /></Lazy> },
      { path: "investigation-diff", element: <Lazy><InvestigationDiffPage /></Lazy> },
      { path: "campaigns", element: <Lazy><CampaignsPage /></Lazy> },
      { path: "threat-actors", element: <Lazy><ThreatActorsPage /></Lazy> },
      { path: "gdpr", element: <Lazy><GdprPage /></Lazy> },
      { path: "maltego", element: <Lazy><MaltegoPage /></Lazy> },
    ],
  },
]);
