import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { Lazy } from "../Lazy";

const InvestigationsPage = lazy(() => import("@/features/investigations/InvestigationsPage").then((m) => ({ default: m.InvestigationsPage })));
const InvestigationDetailPage = lazy(() => import("@/features/investigations/InvestigationDetailPage").then((m) => ({ default: m.InvestigationDetailPage })));
const GraphPage = lazy(() => import("@/features/graph/GraphPage").then((m) => ({ default: m.GraphPage })));
const ScannersPage = lazy(() => import("@/features/scanners/ScannersPage").then((m) => ({ default: m.ScannersPage })));
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
const FacebookIntelPage = lazy(() => import("@/features/facebook-intel").then((m) => ({ default: m.FacebookIntelPage })));
const InstagramIntelPage = lazy(() => import("@/features/instagram-intel").then((m) => ({ default: m.InstagramIntelPage })));
const LinkedInIntelPage = lazy(() => import("@/features/linkedin-intel").then((m) => ({ default: m.LinkedInIntelPage })));
const GitHubIntelPage = lazy(() => import("@/features/github-intel").then((m) => ({ default: m.GitHubIntelPage })));
const VehicleOsintPage = lazy(() => import("@/features/vehicle-osint").then((m) => ({ default: m.VehicleOsintPage })));
const WiglePage = lazy(() => import("@/features/wigle").then((m) => ({ default: m.WiglePage })));
const TechReconPage = lazy(() => import("@/features/tech-recon").then((m) => ({ default: m.TechReconPage })));
const DomainIntelPage = lazy(() => import("@/features/domain-intel/DomainIntelPage").then((m) => ({ default: m.default })));
const SocmintPage = lazy(() => import("@/features/socmint").then((m) => ({ default: m.SocmintPage })));
const CredentialIntelPage = lazy(() => import("@/features/credential-intel").then((m) => ({ default: m.CredentialIntelPage })));
const ImintPage = lazy(() => import("@/features/imint").then((m) => ({ default: m.ImintPage })));
const WatchlistPage = lazy(() => import("@/features/watchlist/WatchlistPage").then((m) => ({ default: m.WatchlistPage })));
const CampaignsPage = lazy(() => import("@/features/campaigns/CampaignsPage").then((m) => ({ default: m.CampaignsPage })));
const ThreatActorsPage = lazy(() => import("@/features/threat-actors/ThreatActorsPage").then((m) => ({ default: m.ThreatActorsPage })));
const DarkWebMonitorPage = lazy(() => import("@/features/dark-web/DarkWebMonitorPage").then((m) => ({ default: m.DarkWebMonitorPage })));
const PassiveDnsPage = lazy(() => import("@/features/passive-dns/PassiveDnsPage").then((m) => ({ default: m.PassiveDnsPage })));
const DigitalFootprintPage = lazy(() => import("@/features/digital-footprint/DigitalFootprintPage").then((m) => ({ default: m.DigitalFootprintPage })));
const CertTransparencyPage = lazy(() => import("@/features/cert-transparency/CertTransparencyPage").then((m) => ({ default: m.CertTransparencyPage })));
const CryptoTracePage = lazy(() => import("@/features/crypto-trace/CryptoTracePage").then((m) => ({ default: m.CryptoTracePage })));
const CorporateIntelPage = lazy(() => import("@/features/corporate-intel/CorporateIntelPage").then((m) => ({ default: m.CorporateIntelPage })));
const PhoneIntelPage = lazy(() => import("@/features/phone-intel/PhoneIntelPage").then((m) => ({ default: m.PhoneIntelPage })));
const SocialGraphPage = lazy(() => import("@/features/social-graph/SocialGraphPage").then((m) => ({ default: m.SocialGraphPage })));
const BrandProtectionPage = lazy(() => import("@/features/brand-protection/BrandProtectionPage").then((m) => ({ default: m.BrandProtectionPage })));
const CorrelationPage = lazy(() => import("@/features/correlation/CorrelationPage").then((m) => ({ default: m.CorrelationPage })));
const EvidenceLockerPage = lazy(() => import("@/features/evidence-locker/EvidenceLockerPage").then((m) => ({ default: m.EvidenceLockerPage })));
const DeepResearchPage = lazy(() => import("@/features/deep-research").then((m) => ({ default: m.DeepResearchPage })));
const CustomScannerPage = lazy(() => import("@/features/custom-scanner/CustomScannerPage").then((m) => ({ default: m.CustomScannerPage })));
const InvestigationDiffPage = lazy(() => import("@/features/investigation-diff/InvestigationDiffPage").then((m) => ({ default: m.InvestigationDiffPage })));
const MaltegoPage = lazy(() => import("@/features/maltego/MaltegoPage").then((m) => ({ default: m.MaltegoPage })));
const ScannerQuotaPage = lazy(() => import("@/features/scanner-quota/ScannerQuotaPage").then((m) => ({ default: m.ScannerQuotaPage })));
const IOCFeedPage = lazy(() => import("@/features/ioc-feed/IOCFeedPage").then((m) => ({ default: m.IOCFeedPage })));
const AttackSurfacePage = lazy(() => import("@/features/attack-surface/AttackSurfacePage").then((m) => ({ default: m.AttackSurfacePage })));
const ForensicTimelinePage = lazy(() => import("@/features/forensic-timeline/ForensicTimelinePage").then((m) => ({ default: m.ForensicTimelinePage })));
const MultiInvestigationGraphPage = lazy(() => import("@/features/multi-graph/MultiInvestigationGraphPage").then((m) => ({ default: m.MultiInvestigationGraphPage })));
const BrowserExtensionPage = lazy(() => import("@/features/browser-extension/BrowserExtensionPage").then((m) => ({ default: m.BrowserExtensionPage })));
const MitreAttackMatrixPage = lazy(() => import("@/features/mitre-attack").then((m) => ({ default: m.MitreAttackMatrix })));
const WorldMonitorPage = lazy(() => import("@/features/world-monitor/WorldMonitorPage").then((m) => ({ default: m.WorldMonitorDashboard })));

export const osintRoutes: RouteObject[] = [
  { path: "investigations", element: <Lazy name="Investigations"><InvestigationsPage /></Lazy> },
  { path: "investigations/:id", element: <Lazy name="Investigation Detail"><InvestigationDetailPage /></Lazy> },
  { path: "investigations/:id/graph", element: <Lazy name="Investigation Graph"><GraphPage /></Lazy> },
  { path: "scanners", element: <Lazy name="Scanners"><ScannersPage /></Lazy> },
  { path: "playbooks", element: <Lazy name="Playbooks"><PlaybooksPage /></Lazy> },
  { path: "image-checker", element: <Lazy name="Image Checker"><ImageCheckerPage /></Lazy> },
  { path: "doc-metadata", element: <Lazy name="Doc Metadata"><DocMetadataPage /></Lazy> },
  { path: "email-headers", element: <Lazy name="Email Headers"><EmailHeadersPage /></Lazy> },
  { path: "mac-lookup", element: <Lazy name="MAC Lookup"><MacLookupPage /></Lazy> },
  { path: "domain-permutation", element: <Lazy name="Domain Permutation"><DomainPermutationPage /></Lazy> },
  { path: "cloud-exposure", element: <Lazy name="Cloud Exposure"><CloudExposurePage /></Lazy> },
  { path: "stealer-logs", element: <Lazy name="Stealer Logs"><StealerLogsPage /></Lazy> },
  { path: "supply-chain", element: <Lazy name="Supply Chain"><SupplyChainPage /></Lazy> },
  { path: "fediverse", element: <Lazy name="Fediverse"><FediversePage /></Lazy> },
  { path: "facebook-intel", element: <Lazy name="Facebook Intel"><FacebookIntelPage /></Lazy> },
  { path: "instagram-intel", element: <Lazy name="Instagram Intel"><InstagramIntelPage /></Lazy> },
  { path: "linkedin-intel", element: <Lazy name="LinkedIn Intel"><LinkedInIntelPage /></Lazy> },
  { path: "github-intel", element: <Lazy name="GitHub Intel"><GitHubIntelPage /></Lazy> },
  { path: "vehicle-osint", element: <Lazy name="Vehicle OSINT"><VehicleOsintPage /></Lazy> },
  { path: "wigle", element: <Lazy name="WiGLE"><WiglePage /></Lazy> },
  { path: "tech-recon", element: <Lazy name="Tech Recon"><TechReconPage /></Lazy> },
  { path: "domain-intel", element: <Lazy name="Domain Intel"><DomainIntelPage /></Lazy> },
  { path: "socmint", element: <Lazy name="SOCMINT"><SocmintPage /></Lazy> },
  { path: "credential-intel", element: <Lazy name="Credential Intel"><CredentialIntelPage /></Lazy> },
  { path: "imint", element: <Lazy name="IMINT"><ImintPage /></Lazy> },
  { path: "watchlist", element: <Lazy name="Watchlist"><WatchlistPage /></Lazy> },
  { path: "campaigns", element: <Lazy name="Campaigns"><CampaignsPage /></Lazy> },
  { path: "threat-actors", element: <Lazy name="Threat Actors"><ThreatActorsPage /></Lazy> },
  { path: "dark-web", element: <Lazy name="Dark Web Monitor"><DarkWebMonitorPage /></Lazy> },
  { path: "passive-dns", element: <Lazy name="Passive DNS"><PassiveDnsPage /></Lazy> },
  { path: "digital-footprint", element: <Lazy name="Digital Footprint"><DigitalFootprintPage /></Lazy> },
  { path: "cert-transparency", element: <Lazy name="Cert Transparency"><CertTransparencyPage /></Lazy> },
  { path: "crypto-trace", element: <Lazy name="Crypto Tracing"><CryptoTracePage /></Lazy> },
  { path: "corporate-intel", element: <Lazy name="Corporate Intel"><CorporateIntelPage /></Lazy> },
  { path: "phone-intel", element: <Lazy name="Phone Intel"><PhoneIntelPage /></Lazy> },
  { path: "social-graph", element: <Lazy name="Social Graph"><SocialGraphPage /></Lazy> },
  { path: "brand-protection", element: <Lazy name="Brand Protection"><BrandProtectionPage /></Lazy> },
  { path: "correlation", element: <Lazy name="Correlation Engine"><CorrelationPage /></Lazy> },
  { path: "evidence-locker", element: <Lazy name="Evidence Locker"><EvidenceLockerPage /></Lazy> },
  { path: "deep-research", element: <Lazy name="Deep Research"><DeepResearchPage /></Lazy> },
  { path: "custom-scanner", element: <Lazy name="Custom Scanner"><CustomScannerPage /></Lazy> },
  { path: "investigation-diff", element: <Lazy name="Investigation Diff"><InvestigationDiffPage /></Lazy> },
  { path: "maltego", element: <Lazy name="Maltego"><MaltegoPage /></Lazy> },
  { path: "scanner-quota", element: <Lazy name="Scanner Quota"><ScannerQuotaPage /></Lazy> },
  { path: "ioc-feed", element: <Lazy name="IOC Feed"><IOCFeedPage /></Lazy> },
  { path: "attack-surface", element: <Lazy name="Attack Surface"><AttackSurfacePage /></Lazy> },
  { path: "forensic-timeline", element: <Lazy name="Forensic Timeline"><ForensicTimelinePage /></Lazy> },
  { path: "investigations/:id/forensic-timeline", element: <Lazy name="Forensic Timeline"><ForensicTimelinePage /></Lazy> },
  { path: "multi-graph", element: <Lazy name="Multi-Graph Analysis"><MultiInvestigationGraphPage /></Lazy> },
  { path: "browser-extension", element: <Lazy name="Browser Extension"><BrowserExtensionPage /></Lazy> },
  { path: "mitre-attack", element: <Lazy name="MITRE ATT&CK"><MitreAttackMatrixPage /></Lazy> },
  { path: "world-monitor", element: <Lazy name="World Monitor"><WorldMonitorPage /></Lazy> },
];
