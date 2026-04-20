// Type definitions for the SOCMINT (Social Media Intelligence) module.
// Covers modules 21-40 from the SOCMINT domain.

export interface ModuleResultData {
  found: boolean
  data?: Record<string, unknown>
  error?: string | null
  status?: string
  skipped?: boolean
  reason?: string
}

export interface SocmintScan {
  id: string
  target: string
  target_type: 'username' | 'email' | 'phone' | 'url'
  modules_run: string[]
  results: Record<string, ModuleResultData>
  created_at: string
}

export interface SocmintListResponse {
  items: SocmintScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface SocmintRequest {
  target: string
  target_type: 'username' | 'email' | 'phone' | 'url'
  modules?: string[]
}

export interface ModuleGroup {
  key: string
  label: string
  description: string
  modules: string[]
  targetTypes: Array<'username' | 'email' | 'phone' | 'url'>
}

// SOCMINT module groups — maps to modules 21-40
export const SOCMINT_MODULE_GROUPS: ModuleGroup[] = [
  {
    key: 'identity',
    label: 'Identity Discovery',
    description: 'Cross-check username across 3000+ platforms (Modules 21, 32)',
    modules: ['username_crosscheck', 'username_maigret', 'username_whatsmyname', 'username_socialscan'],
    targetTypes: ['username'],
  },
  {
    key: 'behavioral',
    label: 'Behavioral Analysis',
    description: 'Activity patterns, timezone estimation, writing style (Modules 24, 25, 29)',
    modules: ['activity_heatmap', 'language_stylometrics'],
    targetTypes: ['username'],
  },
  {
    key: 'profile',
    label: 'Profile Intelligence',
    description: 'Bio links, credibility scoring, account verification (Modules 27, 34)',
    modules: ['bio_link_extractor', 'profile_credibility'],
    targetTypes: ['username'],
  },
  {
    key: 'network',
    label: 'Network Analysis',
    description: 'LinkedIn connections, Reddit community analysis (Modules 37, 38)',
    modules: ['linkedin_network', 'reddit_karma'],
    targetTypes: ['username'],
  },
  {
    key: 'historical',
    label: 'Historical & Archival',
    description: 'Deleted content, profile snapshots, archived bio changes (Modules 30, 39)',
    modules: ['deleted_post_finder', 'historical_snapshots'],
    targetTypes: ['username'],
  },
  {
    key: 'contact',
    label: 'Contact Discovery',
    description: 'Find email from account (Module 35)',
    modules: ['contact_discovery'],
    targetTypes: ['username', 'email'],
  },
]

export const SOCMINT_MODULE_LABELS: Record<string, string> = {
  username_crosscheck: 'Username Cross-Check (Sherlock)',
  username_maigret: 'Username Enumeration (Maigret)',
  username_whatsmyname: 'Username Lookup (WhatsmyName)',
  username_socialscan: 'Username Availability (SocialScan)',
  activity_heatmap: 'Activity Heatmap',
  language_stylometrics: 'Language Stylometrics',
  bio_link_extractor: 'Bio Link Extractor',
  profile_credibility: 'Profile Credibility Scorer',
  linkedin_network: 'LinkedIn Network Miner',
  reddit_karma: 'Reddit Karma Analysis',
  deleted_post_finder: 'Deleted Post Finder',
  historical_snapshots: 'Historical Snapshots (Wayback)',
  contact_discovery: 'Contact Discovery',
}

// Module 21-40 reference descriptions
export const MODULE_DESCRIPTIONS: Record<string, string> = {
  username_crosscheck: 'Module 21 — Mass username search across 50+ platforms. Reveals handle reuse patterns.',
  username_maigret: 'Module 21 — Extended username enumeration across 3000+ sites via Maigret.',
  username_whatsmyname: 'Module 21 — Username presence check via WhatsmyName database.',
  username_socialscan: 'Module 21 — Real-time username availability checker.',
  activity_heatmap: 'Module 25 — Maps posting hours and days to reveal timezone and daily routine.',
  language_stylometrics: 'Module 29 — Analyzes vocabulary, sentence structure, and writing style for authorship attribution.',
  bio_link_extractor: 'Module 27 — Extracts external URLs from bios for pivoting to other platforms.',
  profile_credibility: 'Module 34 — Behavioral heuristics to score account authenticity (bot detection).',
  linkedin_network: 'Module 37 — Extracts professional connections and organizational structure.',
  reddit_karma: 'Module 38 — Analyzes Reddit post history, karma, and community engagement.',
  deleted_post_finder: 'Module 39 — Searches archival databases (Wayback, Arctic Shift) for removed content.',
  historical_snapshots: 'Module 30 — Tracks profile page snapshots to reveal bio and status changes.',
  contact_discovery: 'Module 35 — Attempts to find email addresses linked to social accounts.',
}
