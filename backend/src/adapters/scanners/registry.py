"""Scanner registry — maps input types to available scanners."""

from collections import defaultdict
from functools import lru_cache

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
from src.adapters.scanners.ffuf_scanner import FFUFScanner
from src.adapters.scanners.jwt_tool_scanner import JWTToolScanner
from src.adapters.scanners.ssti_scanner import SSTIScanner
from src.adapters.scanners.lfi_scanner import LFIScanner
from src.adapters.scanners.xxe_scanner import XXEScanner
from src.adapters.scanners.open_redirect_scanner import OpenRedirectScanner
from src.adapters.scanners.clickjacking_scanner import ClickjackingScanner
from src.adapters.scanners.log4shell_scanner import Log4ShellScanner
from src.adapters.scanners.web_cache_poisoning_scanner import WebCachePoisoningScanner
from src.adapters.scanners.prototype_pollution_scanner import PrototypePollutionScanner
from src.adapters.scanners.shellshock_scanner import ShellshockScanner
from src.adapters.scanners.tls_deep_scanner import TLSDeepScanner
from src.adapters.scanners.paramspider_scanner import ParamSpiderScanner
from src.adapters.scanners.docker_security_scanner import DockerSecurityScanner
from src.adapters.scanners.kubernetes_scanner import KubernetesScanner
from src.adapters.scanners.spring4shell_scanner import Spring4ShellScanner
from src.adapters.scanners.subdomain_permutation_scanner import SubdomainPermutationScanner
from src.adapters.scanners.network_service_scanner import NetworkServiceScanner
from src.adapters.scanners.web_tech_cve_scanner import WebTechCVEScanner
from src.adapters.scanners.email_security_scanner import EmailSecurityScanner
from src.adapters.scanners.api_fuzzer_scanner import APIFuzzerScanner
from src.adapters.scanners.csrf_scanner import CSRFScanner
from src.adapters.scanners.deserialization_scanner import DeserializationScanner
from src.adapters.scanners.dependency_check_scanner import DependencyCheckScanner
from src.adapters.scanners.http403_bypass_scanner import Http403BypassScanner
from src.adapters.scanners.race_condition_scanner import RaceConditionScanner
from src.adapters.scanners.idor_scanner import IDORScanner
from src.adapters.scanners.graphql_security_scanner import GraphQLSecurityScanner
from src.adapters.scanners.oauth_scanner import OAuthScanner
from src.adapters.scanners.crlf_injection_scanner import CRLFInjectionScanner
from src.adapters.scanners.azure_enum_scanner import AzureEnumScanner
from src.adapters.scanners.password_spray_scanner import PasswordSprayScanner
from src.adapters.scanners.business_logic_scanner import BusinessLogicScanner
from src.adapters.scanners.host_header_injection_scanner import HostHeaderInjectionScanner
from src.adapters.scanners.jenkins_scanner import JenkinsScanner
from src.adapters.scanners.file_upload_scanner import FileUploadScanner
from src.adapters.scanners.websocket_scanner import WebSocketScanner
from src.adapters.scanners.elasticsearch_scanner import ElasticsearchScanner
from src.adapters.scanners.confluence_jira_scanner import ConfluenceJiraScanner
from src.adapters.scanners.smtp_relay_scanner import SMTPRelayScanner
from src.adapters.scanners.ssi_injection_scanner import SSIInjectionScanner
from src.adapters.scanners.proxylogon_scanner import ProxyLogonScanner
from src.adapters.scanners.hadoop_scanner import HadoopScanner
from src.adapters.scanners.redis_exploit_scanner import RedisExploitScanner
from src.adapters.scanners.impacket_scanner import ImpacketScanner
from src.adapters.scanners.smb_lateral_scanner import SMBLateralScanner
from src.adapters.scanners.wfuzz_scanner import WFuzzScanner
from src.adapters.scanners.brute_login_scanner import BruteLoginScanner
from src.adapters.scanners.webshell_scanner import WebShellScanner
from src.adapters.scanners.citrix_scanner import CitrixScanner
from src.adapters.scanners.vmware_scanner import VMwareScanner
from src.adapters.scanners.apache_scanner import ApacheScanner
from src.adapters.scanners.iis_scanner import IISScanner
from src.adapters.scanners.xmlrpc_scanner import XMLRPCScanner
from src.adapters.scanners.command_injection_scanner import CommandInjectionScanner
from src.adapters.scanners.http_methods_scanner import HTTPMethodsScanner
from src.adapters.scanners.path_traversal_scanner import PathTraversalScanner
from src.adapters.scanners.whatsapp_scanner import WhatsAppScanner
from src.adapters.scanners.discord_scanner import DiscordScanner
from src.adapters.scanners.gaming_platform_scanner import GamingPlatformScanner
from src.adapters.scanners.phone_cnam_scanner import PhoneCNAMScanner
from src.adapters.scanners.leaked_creds_scanner import LeakedCredsScanner
from src.adapters.scanners.court_records_scanner import CourtRecordsScanner
from src.adapters.scanners.academic_scanner import AcademicScanner
from src.adapters.scanners.patent_scanner import PatentScanner
from src.adapters.scanners.wigle_scanner import WiGLEScanner
from src.adapters.scanners.skype_scanner import SkypeScanner
from src.adapters.scanners.iban_scanner import IBANScanner
from src.adapters.scanners.whois_history_scanner import WhoisHistoryScanner
from src.adapters.scanners.brand_impersonation_scanner import BrandImpersonationScanner
from src.adapters.scanners.dating_app_scanner import DatingAppScanner
from src.adapters.scanners.news_media_scanner import NewsMediaScanner
from src.adapters.scanners.fediverse_deep_scanner import FediverseDeepScanner
from src.adapters.scanners.peoplesearch_scanner import PeopleSearchScanner
from src.adapters.scanners.crypto_clustering_scanner import CryptoClusteringScanner
from src.adapters.scanners.vin_scanner import VINScanner
from src.adapters.scanners.job_intel_scanner import JobIntelScanner
from src.adapters.scanners.darkweb_forum_scanner import DarkWebForumScanner
from src.adapters.scanners.sec_edgar_scanner import SECEdgarScanner
from src.adapters.scanners.telegram_osint_scanner import TelegramOsintScanner
from src.adapters.scanners.shodan_bulk_scanner import ShodanBulkScanner
from src.adapters.scanners.sqlmap_scanner import SQLMapScanner
from src.adapters.scanners.hydra_scanner import HydraScanner
from src.adapters.scanners.gobuster_scanner import GobusterScanner
from src.adapters.scanners.whatweb_scanner import WhatWebScanner
from src.adapters.scanners.commix_scanner import CommixScanner
from src.adapters.scanners.ssrf_scanner import SSRFScanner
from src.adapters.scanners.http_smuggling_scanner import HTTPSmugglingScanner
from src.adapters.scanners.nosqlmap_scanner import NoSQLMapScanner
from src.adapters.scanners.linkfinder_scanner import LinkFinderScanner
from src.adapters.scanners.enum4linux_scanner import Enum4LinuxScanner
from src.adapters.scanners.dnsrecon_scanner import DNSReconScanner
from src.adapters.scanners.s3_bucket_scanner import S3BucketScanner
from src.adapters.scanners.nikto_scanner import NiktoScanner
from src.adapters.scanners.sslscan_scanner import SSLScanScanner
from src.adapters.scanners.wpscan_scanner import WPScanScanner
from src.adapters.scanners.cms_detect_scanner import CMSDetectScanner
from src.adapters.scanners.feroxbuster_scanner import FeroxbusterScanner
from src.adapters.scanners.arjun_scanner import ArjunScanner
from src.adapters.scanners.dalfox_scanner import DalfoxScanner
from src.adapters.scanners.gau_scanner import GAUScanner
from src.adapters.scanners.trufflehog_scanner import TruffleHogScanner
from src.adapters.scanners.gitleaks_scanner import GitleaksScanner
from src.adapters.scanners.masscan_scanner import MasscanScanner
from src.adapters.scanners.corsy_scanner import CorsyScanner
from src.adapters.scanners.cariddi_scanner import CariddiScanner
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
from src.adapters.scanners.username_variation_scanner import UsernameVariationScanner
from src.adapters.scanners.vuln_probe_scanner import VulnProbeScanner
from src.adapters.scanners.whatsmyname_scanner import WhatsmynameScanner
from src.adapters.scanners.whois_scanner import WhoisScanner
from src.adapters.scanners.youtube_scanner import YouTubeScanner
from src.core.domain.entities.types import ScanInputType


class ScannerRegistry:
    """Central registry of all available OSINT scanners.

    Provides O(1) lookup by name and pre-indexed lookup by input type so the
    orchestrator can automatically select the right scanners for a given seed input.
    """

    def __init__(self) -> None:
        self._scanners: list[BaseOsintScanner] = []
        self._by_name: dict[str, BaseOsintScanner] = {}
        self._by_type: dict[ScanInputType, list[BaseOsintScanner]] = defaultdict(list)

    def register(self, scanner: BaseOsintScanner) -> None:
        self._scanners.append(scanner)
        self._by_name[scanner.scanner_name] = scanner
        for input_type in scanner.supported_input_types:
            self._by_type[input_type].append(scanner)

    def get_for_input_type(self, input_type: ScanInputType) -> list[BaseOsintScanner]:
        return list(self._by_type[input_type])

    def get_by_name(self, name: str) -> BaseOsintScanner | None:
        return self._by_name.get(name)

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
    # Username Variation — three scan levels (basic / intermediate / advanced)
    registry.register(UsernameVariationScanner(scan_level="basic"))
    registry.register(UsernameVariationScanner(scan_level="intermediate"))
    registry.register(UsernameVariationScanner(scan_level="advanced"))
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
    # Batch 18 — Kali Linux offensive / web pentesting scanners
    registry.register(NiktoScanner())
    registry.register(SSLScanScanner())
    registry.register(WPScanScanner())
    registry.register(CMSDetectScanner())
    registry.register(FeroxbusterScanner())
    registry.register(ArjunScanner())
    registry.register(DalfoxScanner())
    registry.register(GAUScanner())
    registry.register(TruffleHogScanner())
    registry.register(GitleaksScanner())
    registry.register(MasscanScanner())
    registry.register(CorsyScanner())
    registry.register(CariddiScanner())
    # Batch 19 — Kali Linux offensive tools (round 2)
    registry.register(SQLMapScanner())
    registry.register(HydraScanner())
    registry.register(GobusterScanner())
    registry.register(WhatWebScanner())
    registry.register(CommixScanner())
    registry.register(SSRFScanner())
    registry.register(HTTPSmugglingScanner())
    registry.register(NoSQLMapScanner())
    registry.register(LinkFinderScanner())
    registry.register(Enum4LinuxScanner())
    registry.register(DNSReconScanner())
    registry.register(S3BucketScanner())
    # Batch 20 — Advanced web attack scanners
    registry.register(FFUFScanner())
    registry.register(JWTToolScanner())
    registry.register(SSTIScanner())
    registry.register(LFIScanner())
    registry.register(XXEScanner())
    registry.register(OpenRedirectScanner())
    registry.register(ClickjackingScanner())
    registry.register(Log4ShellScanner())
    registry.register(WebCachePoisoningScanner())
    registry.register(PrototypePollutionScanner())
    registry.register(ShellshockScanner())
    # Batch 22 — Kali Linux tools (round 4): TLS/infra/cloud/API
    registry.register(TLSDeepScanner())
    registry.register(ParamSpiderScanner())
    registry.register(DockerSecurityScanner())
    registry.register(KubernetesScanner())
    registry.register(Spring4ShellScanner())
    registry.register(SubdomainPermutationScanner())
    registry.register(NetworkServiceScanner())
    registry.register(WebTechCVEScanner())
    registry.register(EmailSecurityScanner())
    registry.register(APIFuzzerScanner())
    # Batch 21 — Advanced attack surface scanners
    registry.register(CSRFScanner())
    registry.register(DeserializationScanner())
    registry.register(DependencyCheckScanner())
    registry.register(Http403BypassScanner())
    registry.register(RaceConditionScanner())
    registry.register(IDORScanner())
    registry.register(GraphQLSecurityScanner())
    registry.register(OAuthScanner())
    registry.register(CRLFInjectionScanner())
    registry.register(AzureEnumScanner())
    registry.register(PasswordSprayScanner())
    registry.register(BusinessLogicScanner())
    registry.register(HostHeaderInjectionScanner())
    # Batch 23 — Infrastructure & protocol attack scanners
    registry.register(JenkinsScanner())
    registry.register(FileUploadScanner())
    registry.register(WebSocketScanner())
    registry.register(ElasticsearchScanner())
    registry.register(ConfluenceJiraScanner())
    registry.register(SMTPRelayScanner())
    registry.register(SSIInjectionScanner())
    registry.register(ProxyLogonScanner())
    registry.register(HadoopScanner())
    registry.register(RedisExploitScanner())
    registry.register(ImpacketScanner())
    registry.register(SMBLateralScanner())
    # Batch 24 — Web server CVE + protocol attack scanners
    registry.register(WFuzzScanner())
    registry.register(BruteLoginScanner())
    registry.register(WebShellScanner())
    registry.register(CitrixScanner())
    registry.register(VMwareScanner())
    registry.register(ApacheScanner())
    registry.register(IISScanner())
    registry.register(XMLRPCScanner())
    registry.register(CommandInjectionScanner())
    registry.register(HTTPMethodsScanner())
    registry.register(PathTraversalScanner())
    # Batch 25 — Person OSINT & identity intelligence scanners
    registry.register(WhatsAppScanner())
    registry.register(DiscordScanner())
    registry.register(GamingPlatformScanner())
    registry.register(PhoneCNAMScanner())
    registry.register(LeakedCredsScanner())
    registry.register(CourtRecordsScanner())
    registry.register(AcademicScanner())
    registry.register(PatentScanner())
    registry.register(WiGLEScanner())
    registry.register(SkypeScanner())
    registry.register(IBANScanner())
    registry.register(WhoisHistoryScanner())
    registry.register(BrandImpersonationScanner())
    registry.register(DatingAppScanner())
    registry.register(NewsMediaScanner())
    registry.register(FediverseDeepScanner())
    # Batch 26 — Financial, vehicle, job & people-search intelligence
    registry.register(PeopleSearchScanner())
    registry.register(CryptoClusteringScanner())
    registry.register(VINScanner())
    registry.register(JobIntelScanner())
    registry.register(DarkWebForumScanner())
    registry.register(SECEdgarScanner())
    registry.register(TelegramOsintScanner())
    registry.register(ShodanBulkScanner())
    return registry


@lru_cache(maxsize=1)
def get_default_registry() -> ScannerRegistry:
    """Return a cached singleton scanner registry.

    Uses lru_cache instead of a module-level mutable global so the cache is
    process-safe and can be cleared in tests via get_default_registry.cache_clear().
    """
    return create_default_registry()
