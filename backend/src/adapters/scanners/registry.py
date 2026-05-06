"""Scanner registry — maps input types to available scanners."""

from src.adapters.scanners.amass_scanner import AmassScanner
from src.adapters.scanners.blockchair_scanner import BlockchairScanner
from src.adapters.scanners.blockstream_scanner import BlockstreamScanner
from src.adapters.scanners.nominatim_scanner import NominatimScanner
from src.adapters.scanners.nuclei_scanner import NucleiScanner
from src.adapters.scanners.opensky_scanner import OpenSkyScanner
from src.adapters.scanners.banner_grabber_scanner import BannerGrabberScanner
from src.adapters.scanners.subdomain_takeover_scanner import SubdomainTakeoverScanner
from src.adapters.scanners.common_files_scanner import CommonFilesScanner
from src.adapters.scanners.shared_hosting_scanner import SharedHostingScanner
from src.adapters.scanners.mx_spf_dmarc_scanner import MXSPFDMARCScanner
from src.adapters.scanners.ipv6_mapper_scanner import IPv6MapperScanner
from src.adapters.scanners.traceroute_scanner import TracerouteScanner
from src.adapters.scanners.activity_heatmap_scanner import ActivityHeatmapScanner
from src.adapters.scanners.bio_link_extractor_scanner import BioLinkExtractorScanner
from src.adapters.scanners.profile_credibility_scorer_scanner import ProfileCredibilityScorerScanner
from src.adapters.scanners.language_stylometrics_scanner import LanguageStylemetricsScanner
from src.adapters.scanners.deleted_post_finder_scanner import DeletedPostFinderScanner
from src.adapters.scanners.password_hash_analyzer_scanner import PasswordHashAnalyzerScanner
from src.adapters.scanners.exposed_git_scanner import ExposedGitScanner
from src.adapters.scanners.env_file_miner_scanner import EnvFileMinerScanner
from src.adapters.scanners.domain_squatting_scanner import DomainSquattingScanner
from src.adapters.scanners.compromised_ip_checker_scanner import CompromisedIPCheckerScanner
from src.adapters.scanners.exploit_db_scanner import ExploitDbScanner
from src.adapters.scanners.ransomware_intel_scanner import RansomwareIntelScanner
from src.adapters.scanners.exif_deep_extractor_scanner import ExifDeepExtractorScanner
from src.adapters.scanners.satellite_delta_mapper_scanner import SatelliteDeltaMapperScanner
from src.adapters.scanners.chronolocator_scanner import ChronolocatorScanner
from src.adapters.scanners.visual_landmark_match_scanner import VisualLandmarkMatchScanner
from src.adapters.scanners.license_plate_decoder_scanner import LicensePlateDecoderScanner
from src.adapters.scanners.weather_correlation_scanner import WeatherCorrelationScanner
from src.adapters.scanners.webcam_finder_scanner import WebcamFinderScanner
from src.adapters.scanners.adsb_tracker_scanner import AdsbTrackerScanner as ADSBTrackerScanner
from src.adapters.scanners.maritime_tracker_scanner import MaritimeTrackerScanner
from src.adapters.scanners.neural_image_upscaler_scanner import NeuralImageUpscalerScanner
from src.adapters.scanners.deepfake_detector_scanner import DeepfakeDetectorScanner
from src.adapters.scanners.geolocation_challenge_scanner import GeolocationChallengeScanner
from src.adapters.scanners.street_view_pivot_scanner import StreetViewPivotScanner
from src.adapters.scanners.perspective_distorter_scanner import PerspectiveDistorterScanner
from src.adapters.scanners.vegetation_soil_mapper_scanner import VegetationSoilMapperScanner
from src.adapters.scanners.building_height_estimator_scanner import BuildingHeightEstimatorScanner
from src.adapters.scanners.social_media_geofence_scanner import SocialMediaGeofenceScanner
from src.adapters.scanners.public_wifi_mapper_scanner import PublicWifiMapperScanner
from src.adapters.scanners.historical_map_overlay_scanner import HistoricalMapOverlayScanner
from src.adapters.scanners.forensic_image_auditor_scanner import ForensicImageAuditorScanner
from src.adapters.scanners.xss_payload_tester_scanner import XSSPayloadTesterScanner
from src.adapters.scanners.sqli_vulnerability_scanner import SQLiVulnerabilityScanner
from src.adapters.scanners.fuzzing_engine_scanner import FuzzingEngineScanner
from src.adapters.scanners.directory_buster_scanner import DirectoryBusterScanner
from src.adapters.scanners.brute_force_ssh_scanner import BruteForceSSHScanner
from src.adapters.scanners.binary_string_extractor_scanner import BinaryStringExtractorScanner
from src.adapters.scanners.jwt_security_auditor_scanner import JWTSecurityAuditorScanner
from src.adapters.scanners.cloud_storage_hunter_scanner import CloudStorageHunterScanner
from src.adapters.scanners.cicd_secret_scanner import CICDSecretScanner
from src.adapters.scanners.api_security_scanner import APISecurityScanner
from src.adapters.scanners.dangling_dns_scanner import DanglingDNSScanner
from src.adapters.scanners.threat_intel_aggregator_scanner import ThreatIntelAggregatorScanner
from src.adapters.scanners.graphql_depth_auditor_scanner import GraphQLDepthAuditorScanner
from src.adapters.scanners.kerberoasting_scanner import KerberoastingScanner
from src.adapters.scanners.container_escape_auditor_scanner import ContainerEscapeAuditorScanner
from src.adapters.scanners.ad_cs_abuse_scanner import ADCSAbuseScanner
from src.adapters.scanners.encryption_sandbox_scanner import EncryptionSandboxScanner
from src.adapters.scanners.ids_rule_generator_scanner import IDSRuleGeneratorScanner
from src.adapters.scanners.aws_iam_auditor_scanner import AWSIAMAuditorScanner
from src.adapters.scanners.payload_evasion_engine_scanner import PayloadEvasionEngineScanner
from src.adapters.scanners.asn_scanner import ASNScanner
from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.bgp_scanner import BGPHijackScanner
from src.adapters.scanners.breach_scanner import BreachScanner
from src.adapters.scanners.cert_scanner import CertTransparencyScanner
from src.adapters.scanners.circl_hashlookup_scanner import CIRLHashlookupScanner
from src.adapters.scanners.cloud_asset_scanner import CloudAssetScanner
from src.adapters.scanners.cloud_metadata_scanner import CloudMetadataScanner
from src.adapters.scanners.companies_house_scanner import CompaniesHouseScanner
from src.adapters.scanners.crypto_scanner import CryptoAddressScanner
from src.adapters.scanners.darkweb_scanner import DarkWebScanner
from src.adapters.scanners.dns_bruteforce_scanner import DNSBruteforceScanner
from src.adapters.scanners.dns_scanner import DNSScanner
from src.adapters.scanners.dnsdumpster_scanner import DNSDumpsterScanner
from src.adapters.scanners.dnsx_scanner import DnsxScanner
from src.adapters.scanners.dorking_scanner import GoogleDorkScanner
from src.adapters.scanners.email_header_scanner import EmailHeaderScanner
from src.adapters.scanners.facebook_scanner import FacebookScanner
from src.adapters.scanners.favicon_scanner import FaviconHashScanner
from src.adapters.scanners.gdelt_scanner import GDELTScanner
from src.adapters.scanners.geoip_scanner import GeoIPScanner
from src.adapters.scanners.ghunt_scanner import GhuntScanner
from src.adapters.scanners.github_scanner import GitHubScanner
from src.adapters.scanners.google_scanner import GoogleAccountScanner
from src.adapters.scanners.greynoise_scanner import GreyNoiseScanner
from src.adapters.scanners.h8mail_scanner import H8mailScanner
from src.adapters.scanners.hackertarget_scanner import HackerTargetScanner
from src.adapters.scanners.holehe_scanner import HoleheScanner
from src.adapters.scanners.httpx_probe_scanner import HttpxProbeScanner
from src.adapters.scanners.ignorant_scanner import IgnorantScanner
from src.adapters.scanners.instagram_scanner import InstagramScanner
from src.adapters.scanners.internetdb_scanner import InternetDBScanner
from src.adapters.scanners.ipapi_scanner import IPAPIScanner
from src.adapters.scanners.ipinfo_scanner import IPInfoScanner
from src.adapters.scanners.linkedin_company_scanner import LinkedInCompanyScanner
from src.adapters.scanners.linkedin_scanner import LinkedInScanner
from src.adapters.scanners.maigret_scanner import MaigretScanner
from src.adapters.scanners.malwarebazaar_scanner import MalwareBazaarScanner
from src.adapters.scanners.metadata_scanner import MetadataScanner
from src.adapters.scanners.metagoofil_scanner import MetagoofilScanner
from src.adapters.scanners.pyexiftool_scanner import ExifToolEnhancedScanner
from src.adapters.scanners.apkleaks_scanner import APKLeaksScanner
from src.adapters.scanners.bevigil_scanner import BeVigilScanner
from src.adapters.scanners.etherscan_enhanced_scanner import EtherscanEnhancedScanner
from src.adapters.scanners.theharvester_enhanced_scanner import TheHarvesterEnhancedScanner
from src.adapters.scanners.llm_entity_scanner import LLMEntityScanner
from src.adapters.scanners.ais_vessel_scanner import AISVesselScanner
from src.adapters.scanners.opencorporates_scanner import OpenCorporatesScanner
from src.adapters.scanners.opensanctions_scanner import OpenSanctionsScanner
from src.adapters.scanners.otx_scanner import OTXScanner
from src.adapters.scanners.overpass_scanner import OverpassScanner
from src.adapters.scanners.paste_scanner import PasteSitesScanner
from src.adapters.scanners.phone_scanner import PhoneScanner
from src.adapters.scanners.photon_scanner import PhotonScanner
from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner
from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner
from src.adapters.scanners.playwright_vat import VATStatusScanner
from src.adapters.scanners.pwndb_scanner import PwnDBScanner
from src.adapters.scanners.reddit_scanner import RedditScanner
from src.adapters.scanners.ripestat_scanner import RIPEStatScanner
from src.adapters.scanners.secedgar_scanner import SECEdgarScanner
from src.adapters.scanners.sherlock_scanner import SherlockScanner
from src.adapters.scanners.shodan_scanner import ShodanScanner
from src.adapters.scanners.socialscan_scanner import SocialscanScanner
from src.adapters.scanners.subdomain_scanner import SubdomainScanner
from src.adapters.scanners.subfinder_scanner import SubfinderScanner
from src.adapters.scanners.sublist3r_scanner import Sublist3rScanner
from src.adapters.scanners.telegram_scanner import TelegramScanner
from src.adapters.scanners.theharvester_scanner import TheHarvesterScanner
from src.adapters.scanners.threatfox_scanner import ThreatFoxScanner
from src.adapters.scanners.tiktok_scanner import TikTokScanner
from src.adapters.scanners.toutatis_scanner import ToutatisScanner
from src.adapters.scanners.tracking_scanner import TrackingCodeScanner
from src.adapters.scanners.twitter_scanner import TwitterScanner
from src.adapters.scanners.urlhaus_scanner import URLhausScanner
from src.adapters.scanners.urlscan_scanner import URLScanScanner
from src.adapters.scanners.viewdns_scanner import ViewDNSScanner
from src.adapters.scanners.virustotal_scanner import VirusTotalScanner
from src.adapters.scanners.waf_scanner import WAFDetectScanner
from src.adapters.scanners.wayback_cdx_scanner import WaybackCdxScanner
from src.adapters.scanners.wayback_scanner import WaybackScanner
from src.adapters.scanners.username_intel_scanner import UsernameIntelScanner
from src.adapters.scanners.vuln_probe_scanner import VulnProbeScanner
from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner
from src.adapters.scanners.whois_scanner import WhoisScanner
from src.adapters.scanners.youtube_scanner import YouTubeScanner
from src.core.domain.entities.types import ScanInputType


class ScannerRegistry:
    """Central registry of all available OSINT scanners.

    Provides lookup by input type so the orchestrator can automatically
    select the right scanners for a given seed input.
    """

    def __init__(self) -> None:
        self._scanners: list[BaseOsintScanner] = []

    def register(self, scanner: BaseOsintScanner) -> None:
        self._scanners.append(scanner)

    def get_for_input_type(self, input_type: ScanInputType) -> list[BaseOsintScanner]:
        return [s for s in self._scanners if s.supports(input_type)]

    def get_by_name(self, name: str) -> BaseOsintScanner | None:
        for s in self._scanners:
            if s.scanner_name == name:
                return s
        return None

    @property
    def all_scanners(self) -> list[BaseOsintScanner]:
        return list(self._scanners)


def create_default_registry() -> ScannerRegistry:
    """Create a registry with all built-in scanners."""
    registry = ScannerRegistry()
    registry.register(UsernameIntelScanner())
    registry.register(VulnProbeScanner())
    registry.register(HoleheScanner())
    registry.register(MaigretScanner())
    registry.register(PlaywrightKRSScanner())
    registry.register(PlaywrightCEIDGScanner())
    registry.register(VATStatusScanner())
    registry.register(WhoisScanner())
    registry.register(DNSScanner())
    registry.register(ShodanScanner())
    registry.register(GeoIPScanner())
    registry.register(CertTransparencyScanner())
    registry.register(BreachScanner())
    registry.register(PhoneScanner())
    registry.register(VirusTotalScanner())
    registry.register(GoogleAccountScanner())
    registry.register(LinkedInScanner())
    registry.register(TwitterScanner())
    registry.register(FacebookScanner())
    registry.register(InstagramScanner())
    registry.register(SubdomainScanner())
    registry.register(WaybackScanner())
    registry.register(GitHubScanner())
    registry.register(PasteSitesScanner())
    registry.register(TelegramScanner())
    registry.register(TikTokScanner())
    registry.register(YouTubeScanner())
    registry.register(RedditScanner())
    registry.register(DarkWebScanner())
    registry.register(ASNScanner())
    # New scanners — infrastructure fingerprinting & metadata
    registry.register(DNSBruteforceScanner())
    registry.register(TrackingCodeScanner())
    registry.register(MetadataScanner())
    # New scanners — Feature batch 2
    registry.register(FaviconHashScanner())
    registry.register(BGPHijackScanner())
    registry.register(CloudAssetScanner())
    registry.register(EmailHeaderScanner())
    registry.register(CryptoAddressScanner())
    registry.register(GoogleDorkScanner())
    registry.register(LinkedInCompanyScanner())
    registry.register(CloudMetadataScanner())
    # New scanners — Feature batch 3: IP enrichment, DNS recon, WAF detection
    registry.register(InternetDBScanner())
    registry.register(HackerTargetScanner())
    registry.register(URLScanScanner())
    registry.register(ViewDNSScanner())
    registry.register(IPAPIScanner())
    registry.register(IPInfoScanner())
    registry.register(DNSDumpsterScanner())
    registry.register(RIPEStatScanner())
    registry.register(WAFDetectScanner())
    # New scanners — Feature batch 4: subdomain recon tools
    registry.register(SubfinderScanner())
    registry.register(Sublist3rScanner())
    registry.register(AmassScanner())
    registry.register(DnsxScanner())
    # New scanners — Feature batch 5: username / account discovery
    registry.register(SocialscanScanner())
    registry.register(WhatsmynameScanner())
    registry.register(SherlockScanner())
    registry.register(GhuntScanner())
    registry.register(ToutatisScanner())
    registry.register(IgnorantScanner())
    # New scanners — Feature batch 6: web crawling / archival
    registry.register(WaybackCdxScanner())
    registry.register(PhotonScanner())
    registry.register(MetagoofilScanner())
    # New scanners — Feature batch 7: threat intelligence
    registry.register(GreyNoiseScanner())
    registry.register(OTXScanner())
    registry.register(ThreatFoxScanner())
    registry.register(URLhausScanner())
    registry.register(MalwareBazaarScanner())
    registry.register(CIRLHashlookupScanner())
    registry.register(PwnDBScanner())
    registry.register(H8mailScanner())
    # New scanners — Feature batch 8: corporate / financial intelligence
    registry.register(OpenCorporatesScanner())
    registry.register(CompaniesHouseScanner())
    registry.register(SECEdgarScanner())
    registry.register(OpenSanctionsScanner())
    registry.register(GDELTScanner())
    # New scanners — Feature batch 9: theHarvester & HTTP probing
    registry.register(TheHarvesterScanner())
    registry.register(HttpxProbeScanner())
    # New scanners — Feature batch 10: geospatial
    registry.register(OverpassScanner())
    # New scanners — Feature batch 11: metadata, APK, blockchain, LLM, AIS
    registry.register(ExifToolEnhancedScanner())
    registry.register(APKLeaksScanner())
    registry.register(BeVigilScanner())
    registry.register(EtherscanEnhancedScanner())
    registry.register(TheHarvesterEnhancedScanner())
    registry.register(LLMEntityScanner())
    registry.register(AISVesselScanner())
    # Batch 12 — crypto / geo / vuln
    registry.register(BlockchairScanner())
    registry.register(BlockstreamScanner())
    registry.register(NominatimScanner())
    registry.register(NucleiScanner())
    registry.register(OpenSkyScanner())
    # Batch 13 — technical recon scanners
    registry.register(BannerGrabberScanner())
    registry.register(SubdomainTakeoverScanner())
    registry.register(CommonFilesScanner())
    registry.register(SharedHostingScanner())
    registry.register(MXSPFDMARCScanner())
    registry.register(IPv6MapperScanner())
    registry.register(TracerouteScanner())
    # Batch 14 — SOCMINT specialized scanners
    registry.register(ActivityHeatmapScanner())
    registry.register(BioLinkExtractorScanner())
    registry.register(ProfileCredibilityScorerScanner())
    registry.register(LanguageStylemetricsScanner())
    registry.register(DeletedPostFinderScanner())
    # Batch 15 — Credential Intelligence scanners (Domain III, Modules 41-60)
    registry.register(PasswordHashAnalyzerScanner())
    registry.register(ExposedGitScanner())
    registry.register(EnvFileMinerScanner())
    registry.register(DomainSquattingScanner())
    registry.register(CompromisedIPCheckerScanner())
    registry.register(ExploitDbScanner())
    registry.register(RansomwareIntelScanner())
    # Batch 16 — IMINT/GEOINT scanners (Domain IV, Modules 61-80)
    registry.register(ExifDeepExtractorScanner())
    registry.register(SatelliteDeltaMapperScanner())
    registry.register(ChronolocatorScanner())
    registry.register(VisualLandmarkMatchScanner())
    registry.register(LicensePlateDecoderScanner())
    registry.register(WeatherCorrelationScanner())
    registry.register(WebcamFinderScanner())
    registry.register(ADSBTrackerScanner())
    registry.register(MaritimeTrackerScanner())
    registry.register(NeuralImageUpscalerScanner())
    # Batch 16 continued — Media forensics, geospatial intelligence & WiFi OSINT
    registry.register(DeepfakeDetectorScanner())
    registry.register(GeolocationChallengeScanner())
    registry.register(StreetViewPivotScanner())
    registry.register(PerspectiveDistorterScanner())
    registry.register(VegetationSoilMapperScanner())
    registry.register(BuildingHeightEstimatorScanner())
    registry.register(SocialMediaGeofenceScanner())
    registry.register(PublicWifiMapperScanner())
    registry.register(HistoricalMapOverlayScanner())
    registry.register(ForensicImageAuditorScanner())
    # Batch 17 — Infrastructure & Exploitation scanners (Domain V, Modules 81-127)
    registry.register(XSSPayloadTesterScanner())
    registry.register(SQLiVulnerabilityScanner())
    registry.register(FuzzingEngineScanner())
    registry.register(DirectoryBusterScanner())
    registry.register(BruteForceSSHScanner())
    registry.register(BinaryStringExtractorScanner())
    registry.register(JWTSecurityAuditorScanner())
    registry.register(CloudStorageHunterScanner())
    registry.register(CICDSecretScanner())
    registry.register(APISecurityScanner())
    registry.register(DanglingDNSScanner())
    registry.register(ThreatIntelAggregatorScanner())
    registry.register(GraphQLDepthAuditorScanner())
    registry.register(KerberoastingScanner())
    registry.register(ContainerEscapeAuditorScanner())
    registry.register(ADCSAbuseScanner())
    registry.register(EncryptionSandboxScanner())
    registry.register(IDSRuleGeneratorScanner())
    registry.register(AWSIAMAuditorScanner())
    registry.register(PayloadEvasionEngineScanner())
    return registry


_default_registry: ScannerRegistry | None = None  # Reset on module reload


def get_default_registry() -> ScannerRegistry:
    """Return a cached singleton scanner registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_registry()
    return _default_registry
