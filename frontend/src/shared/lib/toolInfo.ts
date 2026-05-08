export interface ToolInfo {
  /** One-sentence summary shown below the page title. */
  short: string;
  /** Full description shown in the "Learn more" modal. */
  details: string;
}

export const TOOL_INFO: Record<string, ToolInfo> = {
  'world-monitor': {
    short: 'Real-time geopolitical intelligence dashboard — aggregates 60+ RSS feeds, conflict events, market signals, and satellite fire data into a unified situational awareness picture.',
    details: `World Monitor is a live geopolitical intelligence platform built on open-source signals. It continuously ingests more than 60 RSS feeds spanning nine categories — geopolitics, military, cyber, economy, climate, disasters, health, energy, and technology — and surfaces them as a unified, searchable news stream with 5-minute refresh cycles.

The dashboard is architected around a multi-signal convergence model. News items are clustered by semantic similarity (step 5) so you can see when multiple sources are reporting the same developing event. A Country Intelligence Index (CII, step 8) synthesises twelve independent signals per country — conflict event frequency, news sentiment, market volatility, flight anomalies, GPS disruptions, FIRMS fire density, cyber incidents, and humanitarian crises — into a 0–100 composite score that updates every 15 minutes.

The cross-stream correlation engine (step 9) automatically flags when signals from different domains converge: a military-category news spike coinciding with a confirmed ACLED conflict event in the same country, a market drop paired with negative sentiment, or an evacuation flight pattern collocating with a FIRMS fire cluster. Each convergence is scored and surfaced as an alert with an evidence trail.

The map layer (step 4) uses deck.gl WebGL rendering to display up to 5,000 event markers, a news density heatmap, active flight tracks from OpenSky Network, and arc connections between correlated countries — all switchable via layer toggles.

All data is cached in Redis with tiered TTLs (fast 5 min → daily 24 h) and served via a single bootstrap endpoint for sub-800 ms cold-start load. The module exposes a \`<WorldMonitorDashboard />\` React component mountable in any parent shell, and its backend runs under the \`/worldmonitor/api\` prefix for clean gateway routing.`,
  },
  'deep-research': {
    short: 'Multi-source OSINT orchestration — correlates social media, phone, KRS/CEIDG, dark web leaks and AI synthesis into a unified person/entity profile.',
    details: `Deep Research is the flagship investigation module. It accepts any combination of identifiers — first name, last name, email, username, phone number, NIP, or company name — and fans out across every relevant OSINT source simultaneously.

Results are streamed in real time as each module completes: social-media footprint (SOCMINT), email intelligence via Holehe and H8mail, phone carrier and owner lookup, KRS/CEIDG Polish business registry checks, and dark-web credential leak correlation.

The AI synthesis layer reads all raw findings and writes a structured narrative — key facts, risk indicators, relationship map — so you can move from raw data to actionable intelligence in minutes rather than hours.

Use this tool when you need a broad, deep profile of an unknown person or entity before deciding which specialist scanners to run next.`,
  },

  'image-checker': {
    short: 'Extracts hidden EXIF metadata, GPS coordinates, camera model, and edit history from uploaded images.',
    details: `The Image Metadata Analyzer parses EXIF, IPTC, and XMP metadata embedded in JPEG, PNG, TIFF, HEIC, and RAW files. This data is often invisible to the naked eye but reveals a wealth of investigative context.

GPS coordinates embedded by smartphones can pinpoint where a photo was taken down to a few metres. Camera make and model, lens focal length, and shutter settings help confirm or disprove device ownership claims. Software tags show which editing tools (Photoshop, Lightroom, GIMP) were used and when, which is useful for authenticity verification.

Results are stored in the analysis history so you can revisit and compare findings across multiple images in the same investigation.`,
  },

  'doc-metadata': {
    short: 'Reveals author, revision history, software origin, and hidden properties inside PDF and Office documents.',
    details: `Document Metadata Extractor reads the internal properties embedded in PDF, DOCX, XLSX, PPTX, ODT, and similar office formats. These properties are set automatically by the authoring software and often contain information that the document's creator never intended to share.

Common findings include the original author's username (matching an Active Directory account), the company name from the software license, document revision count and editing time, template filenames, and printer/software UUIDs.

For PDF files the tool also extracts producer, creator application, PDF version, and any embedded JavaScript. For Office XML formats it parses the core properties, app properties, and custom document properties.

This data is especially valuable for attribution — connecting an anonymous document back to its creator or organisation.`,
  },

  'email-headers': {
    short: 'Traces the full delivery path of an email, exposing originating IPs, mail servers, and SPF/DKIM/DMARC results.',
    details: `Email Header Analyzer parses the raw Received headers that mail servers append as a message travels from sender to recipient. Each hop adds a timestamp and IP address, making it possible to reconstruct the exact delivery route.

The tool resolves each relay IP to its hostname and geographic location, flags any inconsistencies in timestamps (which can indicate header forgery), and evaluates SPF, DKIM, and DMARC records to determine whether the sending domain is legitimate.

Phishing investigation is the primary use case: headers quickly reveal whether the sender's domain matches its claimed identity, which mail relay actually injected the message, and whether authentication mechanisms were bypassed.

Paste the full raw header block (copy from your mail client's "View Source" or "Show Original" option) into the input field.`,
  },

  'mac-lookup': {
    short: 'Identifies the manufacturer and device type for any MAC address using the IEEE OUI registry.',
    details: `MAC Address Lookup queries the IEEE Organizationally Unique Identifier (OUI) registry to resolve the first 24 bits of a MAC address to the hardware manufacturer. This is useful when analysing network captures, device inventories, or access logs.

Beyond the manufacturer name, the tool also flags special MAC address types: universally vs. locally administered, unicast vs. multicast, and well-known reserved addresses. It detects randomised MAC addresses (used by modern iOS, Android, and Windows devices to protect privacy on public networks).

Typical use cases include identifying unknown devices on a network, correlating a device seen in one location with a manufacturer in a supply-chain investigation, or validating that a MAC address belongs to the hardware vendor claimed in an asset register.`,
  },

  'domain-permutation': {
    short: 'Generates typosquatting and look-alike domain variants and checks which are registered or resolving.',
    details: `Domain Permutation generates hundreds of domain name variants based on common typographical, homoglyph, and structural mutations of a target domain. It then checks each variant for DNS registration, active A/MX records, and HTTP reachability.

Mutation strategies include: character transpositions, additions, deletions, keyboard adjacency errors, homoglyph substitutions (e.g. rn → m, 0 → o), subdomain insertions, TLD variations, bitsquatting, and combosquatting with brand terms.

This is the primary tool for brand-protection monitoring — discovering domains that could be used for phishing, credential harvesting, or brand impersonation before an incident occurs. Results include a DNS status, registration date (where available), and a risk score based on how closely the variant resembles the original.`,
  },

  'cloud-exposure': {
    short: 'Enumerates publicly accessible cloud storage buckets, blobs, and objects across AWS, Azure, and GCP.',
    details: `Cloud Exposure Scanner discovers misconfigured cloud storage assets associated with a target organisation. It generates bucket and container name variants from a seed domain or company name, then checks each against the public endpoints of AWS S3, Azure Blob Storage, Google Cloud Storage, and DigitalOcean Spaces.

For any accessible resource it attempts to list contents, capturing file names, sizes, and last-modified dates without downloading files. Common findings include database backups, source code archives, configuration files containing credentials, and sensitive documents that were inadvertently made public.

The results feed directly into the Evidence Locker and can be attached to an investigation to support a cloud misconfiguration finding during a pentest engagement.`,
  },

  'stealer-logs': {
    short: 'Searches stealer malware log databases for credentials, cookies, and system info tied to an email or domain.',
    details: `Stealer Logs Intelligence queries aggregated databases of logs exfiltrated by information-stealing malware (RedLine, Vidar, Raccoon, LummaC2, etc.). These logs contain browser-saved passwords, session cookies, autofill data, and system fingerprints.

Search by email address (to find accounts associated with a specific person) or by domain (to find all credentials harvested from employees of an organisation). Results include the infected machine's hostname, country, infected date, and the list of compromised credentials and services.

This intelligence is used by threat intelligence teams to proactively notify employees of active credential exposure, by red teams to enumerate valid credentials before an engagement, and by investigators to understand the scope of a breach.`,
  },

  'supply-chain': {
    short: 'Analyses software package dependencies for known vulnerabilities, malicious packages, and maintainer risks.',
    details: `Supply Chain Risk Analyzer examines the dependency tree of npm, PyPI, RubyGems, and Maven packages for known vulnerabilities (via OSV and NVD), typosquatting (packages with names similar to popular ones), abandoned maintainer accounts, and unusual publish patterns.

For each package it reports CVE severity scores, days since last update, number of maintainers (single-maintainer packages carry higher risk), and whether the package has known malicious versions in its history.

This tool is essential for software composition analysis (SCA) during security assessments and helps engineering teams prioritise dependency upgrades based on actual exploitability rather than raw CVE count.`,
  },

  'fediverse': {
    short: 'Searches federated social networks (Mastodon, Pleroma, Misskey) for accounts and posts matching a query.',
    details: `Fediverse Intelligence searches the decentralised ActivityPub ecosystem — including Mastodon, Pleroma, Misskey, Calckey, and Pixelfed instances — for user accounts, posts, and hashtags related to a target identity or topic.

Because the Fediverse is decentralised, no single API covers everything. The tool queries multiple large instances and directory services, then deduplicates and ranks results by relevance. It captures display name, handle, bio, post count, follower count, and the most recent posts.

Fediverse accounts are increasingly used by privacy-conscious individuals and groups who have migrated away from centralised platforms, making this search essential for comprehensive social-media coverage.`,
  },

  'wigle': {
    short: 'Geolocates WiFi networks and BSSIDs using the WiGLE crowdsourced wardriving database.',
    details: `WiGLE WiFi Intelligence queries the WiGLE (Wireless Geographic Logging Engine) database, which contains over 1 billion crowdsourced wireless network observations. By searching for an SSID or BSSID (MAC address), you can determine where a WiFi network was physically observed and when.

This is valuable for geolocation without GPS: if a subject's device has connected to a known network, or if a photo's metadata contains a connected BSSID, WiGLE can place that device within a geographic area. It also reveals when a network was first and last observed, which can establish a timeline.

Common investigative uses include confirming a claimed location, tracing the movements of a device across time, and identifying the home or work network of a subject from their device's probe requests.`,
  },

  'tech-recon': {
    short: 'Fingerprints the technology stack of a web application — frameworks, CDNs, analytics, CMS, and server software.',
    details: `Technology Reconnaissance sends a series of crafted HTTP requests to a target URL and analyses the responses — headers, cookies, HTML structure, JavaScript includes, and error pages — to identify the software stack with high confidence.

Detected categories include web servers (nginx, Apache, IIS, Caddy), CMS platforms (WordPress, Drupal, Joomla), JavaScript frameworks (React, Angular, Vue, Next.js), CDN providers (Cloudflare, Fastly, Akamai), analytics platforms, payment processors, and security products (WAF, bot-management).

For each detected technology it reports the confidence level and the version where detectable. Knowing the exact stack is the starting point for targeted vulnerability research and informs which scanners to run next in a penetration test.`,
  },

  'socmint': {
    short: 'Collects and correlates social media intelligence across major platforms for a target username or profile.',
    details: `SOCMINT (Social Media Intelligence) aggregates profile data, post history, follower networks, and cross-platform identity links for a target username, email, or full name across Twitter/X, Reddit, Instagram, TikTok, YouTube, LinkedIn, and GitHub.

The tool uses a combination of public APIs, web scraping (where permitted), and username enumeration (via Sherlock, Maigret, Whatsmyname) to build a comprehensive social footprint. It extracts posting patterns, language and timezone clues, mentioned locations, associated accounts, and linked external identities.

Results are visualised as a social graph within the investigation, and the AI layer synthesises key behavioural patterns and potential aliases. SOCMINT is typically the first module run in a person-of-interest investigation.`,
  },

  'credential-intel': {
    short: 'Correlates email addresses and usernames against breach databases to surface exposed credentials and account activity.',
    details: `Credential Intelligence queries multiple breach and paste databases — including Have I Been Pwned, Dehashed, IntelX, and breach aggregators — to find all known data exposures for a target email address or username.

For each breach it reports the breached service, breach date, data types exposed (password hash, plaintext password, phone, address, etc.), and the hash type where applicable. Where plaintext passwords are available in breach data, the tool flags them for password reuse analysis.

This intelligence is used to assess the credential attack surface of an individual or organisation, identify password reuse patterns across services, and locate additional account identifiers (alternate emails, usernames) that expand the investigation scope.`,
  },

  'imint': {
    short: 'Performs imagery intelligence analysis — reverse image search, geolocation estimation, and EXIF deep-extraction.',
    details: `IMINT (Imagery Intelligence) combines multiple image analysis techniques: reverse image search across TinEye, Google Images, and Yandex to find where an image has appeared online; AI-assisted geolocation estimation based on visual landmarks, vegetation, architecture, and signage; and deep EXIF extraction including GPS track data and embedded thumbnails.

The geolocation challenge feature presents the image alongside map controls and records the analyst's estimated coordinates — useful for collaborative verification exercises. The forensic image auditor checks for signs of digital manipulation (clone stamp, frequency analysis, metadata inconsistencies).

IMINT is particularly valuable for verifying claimed locations in conflict-zone reporting, tracing the original source of viral images, and building a geospatial timeline for a subject.`,
  },

  'scanners': {
    short: 'Run any individual OSINT scanner directly against a target and view the raw structured output.',
    details: `The Scanners page gives direct access to every scanner registered in the platform — over 120 at present — without needing to create a full investigation. Select a scanner, provide the appropriate input (IP address, domain, email, username, etc.), and receive the raw structured result.

Each scanner card shows the input types it supports, its data source, and the last time it was successfully used. Scanners are grouped by category: network intelligence, social media, breach data, DNS, threat intelligence, geospatial, and more.

This is the go-to tool for quick one-off lookups and for verifying that a scanner is working correctly before including it in a playbook or automated investigation.`,
  },

  'custom-scanner': {
    short: 'Build and run custom scanning pipelines by composing existing scanners with conditional logic and transformations.',
    details: `Custom Scanner Builder lets you create reusable scanning pipelines by chaining built-in scanners together with conditional branching, data transformations, and aggregation steps — all without writing code.

Define input variables, connect scanner modules in a visual flow, and specify how the output of one scanner feeds into the next. For example: run a WHOIS lookup, extract the registrant email, then automatically run a breach check and social-media search on that email.

Saved custom scanners appear in the Scanners library and can be included in Playbooks. They run in the same Celery worker pool as built-in scanners, with identical caching and circuit-breaker protection.`,
  },

  'playbooks': {
    short: 'Define automated, repeatable investigation workflows that trigger the right scanners based on target type and findings.',
    details: `Playbooks are structured investigation templates that encode your team's standard operating procedures. Each playbook defines a trigger condition (e.g. "new investigation with IP address"), an ordered set of scanner modules to run, branching conditions based on findings, and notification rules.

When a playbook runs against an investigation, it executes each step in the defined order, passing findings between steps and applying filters. If a step yields a result that meets a condition (e.g. "found active dark web mention"), it branches to additional steps automatically.

Playbooks are the primary mechanism for scaling OSINT workflows across a team — ensuring consistency, reducing analyst time, and capturing institutional knowledge in a shareable, versioned format.`,
  },

  'dark-web': {
    short: 'Monitors Tor hidden services, paste sites, and dark web forums for mentions of your target domains, emails, or brands.',
    details: `Dark Web Monitor continuously indexes Tor hidden services, I2P sites, Freenet forums, and popular paste services for content matching your configured keywords — domain names, email addresses, brand names, employee names, or IP ranges.

Monitored sources include major dark web markets, hacking forums (RaidForums mirrors, Breach Forums), ransomware leak sites, and paste aggregators. New matches trigger alerts in real time via the notification system.

Each finding includes a source URL (accessible via Tor), snippet context, first seen / last seen timestamps, and a category (credential leak, data sale, mention, etc.). Findings are automatically linked to any matching investigation.`,
  },

  'passive-dns': {
    short: 'Queries historical DNS resolution records to reveal past IP addresses, name servers, and domain relationships.',
    details: `Passive DNS Intelligence retrieves historical DNS resolution data from multiple passive DNS providers (DNSDB, SecurityTrails, VirusTotal, RiskIQ). Unlike active DNS lookups that return only current records, passive DNS shows every resolution ever observed for a domain or IP.

For a domain, you can see every IP address it has ever resolved to, every name server it has used, and every subdomain ever observed. For an IP, you can see every domain that has ever resolved to it — invaluable for discovering shared infrastructure and connected threat actor campaigns.

Temporal analysis reveals when a domain was "parked" vs. actively used, when infrastructure changed hands, and which other domains share the same hosting footprint — often the key to pivoting from one indicator to an entire campaign.`,
  },

  'digital-footprint': {
    short: 'Assesses the complete digital footprint of a person or organisation — social presence, data broker exposure, and leaked data.',
    details: `Digital Footprint Score provides a holistic assessment of how much information about a subject is publicly available and where it can be found. It aggregates results from social media, people-search sites, data brokers, breach databases, and public records.

The output is an exposure score (0–100) broken down by category: social media visibility, data broker presence, breach exposure, professional records (LinkedIn, company registries), and government/court records. Each category lists the specific sources where the subject was found.

For individuals, this assessment guides targeted hardening recommendations (opt-outs, privacy settings, data broker removal requests). For organisations, it identifies which employees have the highest public exposure and should be prioritised for security awareness training.`,
  },

  'cert-transparency': {
    short: 'Searches Certificate Transparency logs to enumerate subdomains and track TLS certificate issuance for a domain.',
    details: `Certificate Transparency Log Search queries the publicly available CT log network (crt.sh, Google Argon, Cloudflare Nimbus, and others) for all TLS/SSL certificates ever issued for a target domain and its subdomains.

Every time a certificate is issued by a trusted CA, it must be logged in a CT log — making this one of the most reliable methods for subdomain enumeration. Results include the certificate's common name, SANs (Subject Alternative Names), issuer, issuance date, and expiry.

Beyond enumeration, CT logs reveal certificate issuance spikes (which may indicate an attacker is issuing certificates for phishing domains), wildcard certificates (which may indicate broad internal infrastructure), and certificate mistakes (domains included in error that reveal internal naming conventions).`,
  },

  'crypto-trace': {
    short: 'Traces blockchain transactions and maps fund flows for Bitcoin, Ethereum, and other major cryptocurrencies.',
    details: `Crypto Trace analyses blockchain transaction history for a given wallet address, following fund flows forward and backward through the chain. It uses data from Blockchair, Blockstream, and Etherscan to build a transaction graph showing every address that has sent or received funds to/from the target.

The tool identifies known exchange deposit addresses, mixer/tumbler patterns, cross-chain bridges, and addresses flagged in public sanction lists (OFAC, EU). For Ethereum it also decodes smart contract interactions and ERC-20 token transfers.

Fund flow visualisation is rendered as an interactive graph in the investigation view, with cluster heuristics grouping addresses likely controlled by the same entity. This is the starting point for tracing ransomware payments, fraud proceeds, and sanctions evasion.`,
  },

  'corporate-intel': {
    short: 'Gathers structured business intelligence from company registries, SEC filings, sanctions lists, and corporate databases.',
    details: `Corporate Intelligence aggregates data about a company from multiple authoritative sources: UK Companies House, Polish KRS/CEIDG, OpenCorporates (covering 140+ jurisdictions), SEC EDGAR for US-listed companies, and OpenSanctions for sanctions and PEP screening.

For each company it retrieves: registered address, incorporation date, directors and shareholders (with ownership percentages), filing history, financial statements (where public), related entities (subsidiaries, parent companies), and any sanctions or adverse-media flags.

Beneficial ownership tracing follows the shareholder chain through multiple layers to identify ultimate beneficial owners (UBOs). This is essential for due-diligence investigations, KYC/AML workflows, and understanding the corporate structure of a target organisation.`,
  },

  'phone-intel': {
    short: 'Gathers carrier, line type, owner, and geolocation intelligence for any phone number.',
    details: `Phone Intelligence queries multiple data sources for a given E.164 phone number: carrier and network lookup (HLR), line type classification (mobile, VoIP, landline, toll-free), and registered owner lookup via public records and people-search databases.

Carrier data reveals the originating network and any porting history (which can indicate SIM swapping). VoIP classification flags numbers that are unlikely to belong to a real individual. For mobile numbers, the approximate region of registration is determined from the number range.

Integration with Holehe checks whether the number is linked to accounts on WhatsApp, Telegram, Viber, and other messaging platforms. Results include the subscriber's name where available from public sources.`,
  },

  'social-graph': {
    short: 'Maps social connections and influence networks between identified entities in an investigation.',
    details: `Social Graph Analysis builds a network graph of relationships between entities discovered during an investigation. Nodes represent people, organisations, domains, accounts, or any other entity type; edges represent observed relationships (follows, mentions, shared infrastructure, co-authored content, etc.).

The layout engine applies community detection algorithms to reveal clusters — groups of entities that interact more with each other than with the broader network. Influence scores highlight the most central nodes, which are often key intermediaries or coordinators in a network.

The graph can be exported to Gephi, GraphML, or the Maltego XLSX format for further analysis. It integrates with the investigation's Neo4j graph store, so all manually added relationships and automatically discovered links are reflected in real time.`,
  },

  'brand-protection': {
    short: 'Detects domain squatting, fake social media accounts, phishing pages, and app store impersonation of your brand.',
    details: `Brand Protection Monitor continuously scans for unauthorised use of your brand — logos, trademarks, and domain names — across multiple channels: newly registered domains (via CT logs and WHOIS feeds), social media account names, app store listings (Google Play, Apple App Store), and phishing-feed databases.

Domain monitoring uses the same permutation engine as the Domain Permutation tool, but runs automatically on a schedule and generates alerts only for new findings. Social media monitoring detects accounts using your brand name or logo as profile picture.

Each finding is categorised by risk level and includes recommended takedown procedures and UDRP complaint templates. The tool integrates with abuse reporting APIs for major registrars and platforms to streamline the takedown process.`,
  },

  'correlation': {
    short: 'Cross-references entities across multiple investigations to surface hidden connections and shared indicators.',
    details: `Correlation Engine compares entities — IP addresses, domains, emails, phone numbers, usernames, and hashes — across all investigations in the workspace to find shared indicators that would otherwise be invisible when investigations are siloed.

When the same IP address appears in three separate investigations, for example, the Correlation Engine flags this and creates a cross-investigation link. This is the mechanism for connecting seemingly unrelated incidents to a common threat actor or infrastructure.

Pattern analysis goes beyond exact matches: it detects CIDR overlap (adjacent IPs in the same subnet), registrant similarity (same WHOIS contact across different domains), and temporal correlation (events that occurred within a defined time window). Results are visualised in the Multi-Graph Analysis view.`,
  },

  'evidence-locker': {
    short: 'Securely stores, hashes, and manages chain-of-custody for investigation evidence and collected artefacts.',
    details: `Evidence Locker provides tamper-evident storage for investigation artefacts: screenshots, downloaded files, network captures, exported data, and analyst notes. Every uploaded item is hashed (SHA-256) on ingestion and stored with a custody log recording who uploaded it and when.

Items are tagged with investigation ID, type, and relevance rating, making it easy to build an evidence package at the end of an investigation. The locker supports version history — if a file is updated, the previous version and its hash are preserved.

For formal investigations and legal proceedings, the Evidence Locker generates a chain-of-custody report (PDF) listing every item, its hash, and every access event. Storage is backed by MinIO (S3-compatible), with encryption at rest.`,
  },

  'ioc-feed': {
    short: 'Ingests, de-duplicates, and enriches threat intelligence indicators from STIX, MISP, and commercial feeds.',
    details: `IOC Feed Manager ingests Indicators of Compromise (IOCs) from multiple sources — TAXII/STIX 2.x feeds, MISP instances, OpenCTI exports, CSV uploads, and manual entry. It deduplicates indicators across sources, enriches each with passive DNS, WHOIS, and VirusTotal data, and maintains a confidence score based on source reliability and age.

Indicators can be searched, filtered by type (IP, domain, hash, email, URL, CVE), and exported in STIX 2.1, MISP JSON, or CSV format for ingestion into SIEM and EDR platforms. Integration with the investigation system allows any IOC to be linked to an investigation with a single click.

The feed manager also runs scheduled enrichment jobs, updating confidence scores as indicators age and new context becomes available — ensuring your threat intel stays fresh without manual curation.`,
  },

  'attack-surface': {
    short: 'Enumerates the external attack surface of an organisation — exposed services, open ports, and internet-facing assets.',
    details: `Attack Surface Enumeration discovers and catalogues every internet-facing asset belonging to a target organisation: subdomains, IP ranges, open ports, running services, exposed admin panels, and shadow IT.

Starting from a seed domain or ASN, it uses passive sources (CT logs, Shodan, Censys, BGP data) and active probing (HTTP fingerprinting, port scanning via masscan/nmap profiles) to build a comprehensive asset inventory. Each asset is tagged with its technology stack, open ports, TLS certificate details, and any known vulnerabilities.

The result is an external attack surface map that prioritises assets by risk — highlighting internet-exposed legacy services, forgotten development environments, and services with known critical vulnerabilities. This is the mandatory first step in any external penetration test.`,
  },

  'forensic-timeline': {
    short: 'Reconstructs a chronological event timeline from investigation artefacts, log files, and scanner findings.',
    details: `Forensic Timeline builds a chronological view of all events associated with an investigation by aggregating timestamps from multiple sources: scanner findings (DNS registration dates, certificate issuance, first-seen in breach data), uploaded log files (web server logs, authentication logs, firewall logs), and manual analyst entries.

Events are displayed on an interactive timeline with zoom controls — from a 10-year view down to millisecond precision. Each event is colour-coded by source and type, and can be annotated with analyst notes. Suspicious time gaps, unusual activity spikes, and temporal correlations are highlighted automatically.

The timeline can be exported as a PDF report or as a JSON file for import into Elastic or Splunk. It is linked to the Neo4j graph, so clicking any event shows the full entity context.`,
  },

  'multi-graph': {
    short: 'Renders a combined entity graph spanning multiple investigations to reveal cross-case connections.',
    details: `Multi-Investigation Graph Analysis visualises the combined entity and relationship graph across two or more investigations simultaneously. This reveals shared infrastructure, common threat actors, and overlapping indicators that only become visible when cases are viewed together.

Select any combination of investigations from your workspace and the graph merges their Neo4j subgraphs, deduplicating shared nodes and highlighting cross-investigation edges in a distinct colour. Layout algorithms optimise for readability with up to several thousand nodes.

This is the primary tool for campaign attribution — connecting disparate phishing campaigns, ransomware incidents, or fraud cases to a common origin. The resulting merged graph can be exported to Gephi or Maltego for further analysis.`,
  },

  'watchlist': {
    short: 'Continuously monitors a list of targets for new OSINT findings and triggers alerts on changes.',
    details: `Watchlist runs scheduled OSINT scans against a curated list of targets — domains, email addresses, IP ranges, or person identifiers — and alerts you when new findings appear or existing findings change.

Each watchlist entry has a configurable scan schedule (hourly, daily, weekly) and a set of alert conditions (any new finding, high-severity finding, breach data added, dark web mention). Alerts are delivered via in-app notification, email, or webhook.

The watchlist is designed for continuous monitoring use cases: brand protection, VIP executive monitoring, customer notification of credential breaches, and tracking known threat-actor infrastructure for changes in activity or hosting.`,
  },

  'campaigns': {
    short: 'Groups related investigations, targets, and findings into a structured threat campaign for coordinated analysis.',
    details: `Campaigns provide a higher-level organisational layer above individual investigations. A campaign groups related investigations that share a common threat actor, attack vector, or victim organisation — allowing analysts to track the full scope of a threat over time.

Each campaign has a defined scope (target sectors, geographic regions, date range), a set of TTPs mapped to the MITRE ATT&CK framework, a shared IOC library, and a campaign summary that is updated as new investigations are linked.

Campaign-level reporting generates an executive summary covering the full scope of threat activity, with a timeline, entity graph, and TTP breakdown. This is the format used for formal threat intelligence reports delivered to stakeholders or shared via STIX with partner organisations.`,
  },

  'passive-dns-lookup': {
    short: 'Queries historical DNS resolution records to reveal past IP addresses, name servers, and domain relationships.',
    details: `See Passive DNS tool description above.`,
  },
};
