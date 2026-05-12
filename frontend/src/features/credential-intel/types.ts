// Types for the Credential Intelligence module (Domain III, Modules 41-60).

export interface ModuleResultData {
  found: boolean
  data?: Record<string, unknown>
  error?: string | null
  status?: string
  skipped?: boolean
  reason?: string
}

export interface CredentialIntelScan {
  id: string
  target: string
  target_type: 'email' | 'domain' | 'ip' | 'hash'
  modules_run: string[]
  results: Record<string, ModuleResultData>
  created_at: string
}

export interface CredentialIntelListResponse {
  items: CredentialIntelScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CredentialIntelRequest {
  target: string
  target_type: 'email' | 'domain' | 'ip' | 'hash'
  modules?: string[]
}

export interface ModuleGroup {
  key: string
  label: string
  description: string
  modules: string[]
  targetTypes: Array<'email' | 'domain' | 'ip' | 'hash'>
}

export const CREDENTIAL_INTEL_GROUPS: ModuleGroup[] = [
  {
    key: 'breach',
    label: 'Breach Aggregation',
    description: 'Check email against HIBP, PwnDB, and H8mail breach databases (Module 41)',
    modules: ['breach_hibp', 'breach_pwndb', 'breach_h8mail', 'paste_search'],
    targetTypes: ['email'],
  },
  {
    key: 'hash',
    label: 'Password Hash Analysis',
    description: 'Identify algorithm (MD5/SHA/bcrypt) and compute K^L brute-force complexity (Module 42)',
    modules: ['hash_analyzer'],
    targetTypes: ['hash'],
  },
  {
    key: 'exposure',
    label: 'Code & Config Exposure',
    description: 'Detect exposed .git directories and .env files with hardcoded secrets (Modules 45-47)',
    modules: ['exposed_git', 'env_file_miner'],
    targetTypes: ['domain'],
  },
  {
    key: 'domain_risk',
    label: 'Domain Risk',
    description: 'Typosquatting variants, email spoofing (SPF/DMARC) audit (Modules 48, 52)',
    modules: ['domain_squatting', 'email_spoofing'],
    targetTypes: ['domain'],
  },
  {
    key: 'threat',
    label: 'Threat Intelligence',
    description: 'Malware match, C2 infrastructure detection (Modules 53-54)',
    modules: ['malware_match', 'c2_finder', 'c2_greynoise'],
    targetTypes: ['domain', 'ip'],
  },
  {
    key: 'ip_reputation',
    label: 'IP Reputation',
    description: 'Compromised host check via AbuseIPDB/InternetDB (Module 50)',
    modules: ['compromised_ip'],
    targetTypes: ['ip'],
  },
  {
    key: 'exploit',
    label: 'Exploit & Ransomware',
    description: 'CVE correlation via NVD, ransomware victim matching (Modules 59-60)',
    modules: ['exploit_db', 'ransomware_intel'],
    targetTypes: ['domain'],
  },
]

export const MODULE_LABELS: Record<string, string> = {
  breach_hibp:      'HIBP Breach Check',
  breach_pwndb:     'PwnDB Credential Lookup',
  breach_h8mail:    'H8mail Email Intelligence',
  paste_search:     'Paste Site Monitor',
  hash_analyzer:    'Password Hash Analyzer',
  exposed_git:      'Exposed .git Scanner',
  env_file_miner:   'Environment File Miner',
  leaked_api_keys:  'Leaked API Key Scanner',
  domain_squatting: 'Domain Squatting Detector',
  email_spoofing:   'Email Spoofing Audit (SPF/DMARC)',
  compromised_ip:   'Compromised IP Checker',
  malware_match:    'Malware Sample Match',
  c2_finder:        'Command & Control Finder',
  c2_greynoise:     'C2 GreyNoise Classification',
  exploit_db:       'Exploit DB / CVE Correlator',
  ransomware_intel: 'Ransomware Group Intelligence',
}

export const MODULE_DESCRIPTIONS: Record<string, string> = {
  breach_hibp:      'Module 41 — Checks against 14B+ records in Have I Been Pwned.',
  breach_pwndb:     'Module 41 — Queries ProxyNova COMB and LeakCheck APIs.',
  breach_h8mail:    'Module 41 — Multi-source email breach hunter.',
  paste_search:     'Module 44 — Scans psbdmp.ws for leaked paste data.',
  hash_analyzer:    'Module 42 — Identifies hash algorithm (MD5/SHA/bcrypt/Argon2) and computes K^L crack time.',
  exposed_git:      'Module 45 — Probes /.git/HEAD and config files for exposed repositories.',
  env_file_miner:   'Module 46 — Detects .env, .aws/credentials, and config files with secrets.',
  leaked_api_keys:  'Module 47 — Searches GitHub code for AWS/GCP/API key patterns.',
  domain_squatting: 'Module 48 — Generates 80+ typo variants and resolves which are registered.',
  email_spoofing:   'Module 52 — Audits MX, SPF, DMARC, and DKIM configuration.',
  compromised_ip:   'Module 50 — AbuseIPDB confidence score and abuse category mapping.',
  malware_match:    'Module 53 — VirusTotal reputation and malware classification.',
  c2_finder:        'Module 54 — ThreatFox IOC database for C2 infrastructure.',
  c2_greynoise:     'Module 54 — GreyNoise mass-scanner and malicious IP classification.',
  exploit_db:       'Module 59 — NIST NVD CVE search by keyword/product version.',
  ransomware_intel: 'Module 60 — Ransomwatch victim database check (100+ RaaS groups).',
}

// Complexity table types for educational hash visualization
export interface ComplexityRow {
  length: number
  charset: string
  charset_description: string
  charset_size: number
  combinations: string
  crack_time_sha256_4gpu: string
}
