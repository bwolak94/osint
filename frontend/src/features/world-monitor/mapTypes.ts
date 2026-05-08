export type LayerKey = 'conflict' | 'intel' | 'military' | 'nuclear' | 'cyber' | 'crisis' | 'energy' | 'disaster'

export interface RegionView {
  center: [number, number]
  zoom: number
}

export const REGION_VIEWS: Record<string, RegionView> = {
  'Global':       { center: [20,  10],   zoom: 2  },
  'Europe':       { center: [52,  15],   zoom: 4  },
  'Middle East':  { center: [29,  42],   zoom: 4  },
  'Asia-Pacific': { center: [20,  115],  zoom: 3  },
  'Americas':     { center: [10,  -80],  zoom: 3  },
  'Africa':       { center: [5,   20],   zoom: 3  },
}

export interface MapEvent {
  id: string
  layer: LayerKey
  lat: number
  lng: number
  title: string
  severity: 'high' | 'medium' | 'low'
  timestamp: string
}

export interface LayerConfig {
  key: LayerKey
  label: string
  color: string
  emoji: string
}

export const LAYER_CONFIGS: LayerConfig[] = [
  { key: 'conflict',  label: 'Conflict Zones',   color: '#ef4444', emoji: '🔴' },
  { key: 'intel',     label: 'Intel Hotspots',    color: '#f97316', emoji: '🟠' },
  { key: 'military',  label: 'Military Activity', color: '#3b82f6', emoji: '🔵' },
  { key: 'nuclear',   label: 'Nuclear Sites',     color: '#a855f7', emoji: '🟣' },
  { key: 'cyber',     label: 'Cyber Incidents',   color: '#10b981', emoji: '🟢' },
  { key: 'crisis',    label: 'Humanitarian',      color: '#eab308', emoji: '🟡' },
  { key: 'energy',    label: 'Energy / Infra',    color: '#6366f1', emoji: '🔷' },
  { key: 'disaster',  label: 'Natural Disasters', color: '#fb923c', emoji: '🟧' },
]

// Seeded mock events covering major hotspots
export const MOCK_EVENTS: MapEvent[] = [
  // Conflict
  { id: 'c1',  layer: 'conflict', lat: 48.4,  lng: 31.0,  title: 'Active conflict — Ukraine front',       severity: 'high',   timestamp: new Date(Date.now()-3600000).toISOString()  },
  { id: 'c2',  layer: 'conflict', lat: 31.5,  lng: 34.8,  title: 'Airstrikes reported — Gaza Strip',       severity: 'high',   timestamp: new Date(Date.now()-7200000).toISOString()  },
  { id: 'c3',  layer: 'conflict', lat: 15.5,  lng: 32.5,  title: 'Clashes — Sudan Khartoum region',        severity: 'high',   timestamp: new Date(Date.now()-10800000).toISOString() },
  { id: 'c4',  layer: 'conflict', lat: 12.0,  lng: 15.0,  title: 'Armed group activity — Sahel',           severity: 'medium', timestamp: new Date(Date.now()-86400000).toISOString() },
  { id: 'c5',  layer: 'conflict', lat: 6.0,   lng: -2.0,  title: 'Security incident — West Africa',        severity: 'medium', timestamp: new Date(Date.now()-172800000).toISOString()},
  // Intel
  { id: 'i1',  layer: 'intel',    lat: 35.7,  lng: 51.4,  title: 'Signals collection — Tehran',            severity: 'high',   timestamp: new Date(Date.now()-1800000).toISOString()  },
  { id: 'i2',  layer: 'intel',    lat: 39.9,  lng: 116.4, title: 'OSINT activity — Beijing',               severity: 'medium', timestamp: new Date(Date.now()-5400000).toISOString()  },
  { id: 'i3',  layer: 'intel',    lat: 55.7,  lng: 37.6,  title: 'Diplomatic cables — Moscow',             severity: 'medium', timestamp: new Date(Date.now()-21600000).toISOString() },
  { id: 'i4',  layer: 'intel',    lat: 1.3,   lng: 103.8, title: 'Maritime surveillance — Singapore Strait',severity:'low',   timestamp: new Date(Date.now()-43200000).toISOString() },
  // Military
  { id: 'm1',  layer: 'military', lat: 36.2,  lng: 137.7, title: 'JSDF exercise — Japan Sea',              severity: 'medium', timestamp: new Date(Date.now()-3600000).toISOString()  },
  { id: 'm2',  layer: 'military', lat: 37.5,  lng: 127.0, title: 'ROK-US joint drills — Korean Peninsula', severity: 'medium', timestamp: new Date(Date.now()-7200000).toISOString()  },
  { id: 'm3',  layer: 'military', lat: 26.5,  lng: 55.0,  title: 'Naval movements — Strait of Hormuz',     severity: 'high',   timestamp: new Date(Date.now()-3600000).toISOString()  },
  { id: 'm4',  layer: 'military', lat: 57.0,  lng: 24.1,  title: 'NATO exercises — Baltic region',         severity: 'low',    timestamp: new Date(Date.now()-86400000).toISOString() },
  { id: 'm5',  layer: 'military', lat: -33.9, lng: 18.4,  title: 'Naval patrol — Cape of Good Hope',       severity: 'low',    timestamp: new Date(Date.now()-172800000).toISOString()},
  // Nuclear
  { id: 'n1',  layer: 'nuclear',  lat: 37.5,  lng: 127.9, title: 'DPRK facility activity — Yongbyon',     severity: 'high',   timestamp: new Date(Date.now()-14400000).toISOString() },
  { id: 'n2',  layer: 'nuclear',  lat: 32.5,  lng: 53.0,  title: 'Enrichment — Natanz, Iran',              severity: 'high',   timestamp: new Date(Date.now()-28800000).toISOString() },
  { id: 'n3',  layer: 'nuclear',  lat: 54.0,  lng: 86.0,  title: 'Siberian nuclear complex monitoring',    severity: 'medium', timestamp: new Date(Date.now()-86400000).toISOString() },
  // Cyber
  { id: 'y1',  layer: 'cyber',    lat: 52.5,  lng: 13.4,  title: 'Critical infra attack — Germany',        severity: 'high',   timestamp: new Date(Date.now()-1800000).toISOString()  },
  { id: 'y2',  layer: 'cyber',    lat: 40.7,  lng: -74.0, title: 'Ransomware campaign — US East Coast',    severity: 'high',   timestamp: new Date(Date.now()-5400000).toISOString()  },
  { id: 'y3',  layer: 'cyber',    lat: 51.5,  lng: -0.1,  title: 'Supply chain probe — London',            severity: 'medium', timestamp: new Date(Date.now()-18000000).toISOString() },
  { id: 'y4',  layer: 'cyber',    lat: 35.7,  lng: 139.7, title: 'State-sponsored intrusion — Tokyo',      severity: 'medium', timestamp: new Date(Date.now()-36000000).toISOString() },
  // Crisis
  { id: 'h1',  layer: 'crisis',   lat: 13.5,  lng: 2.1,   title: 'Food insecurity — Niger displacement',   severity: 'high',   timestamp: new Date(Date.now()-43200000).toISOString() },
  { id: 'h2',  layer: 'crisis',   lat: 14.9,  lng: 40.5,  title: 'Refugee movement — Horn of Africa',      severity: 'high',   timestamp: new Date(Date.now()-86400000).toISOString() },
  { id: 'h3',  layer: 'crisis',   lat: 33.9,  lng: 67.7,  title: 'Humanitarian corridor — Afghanistan',    severity: 'medium', timestamp: new Date(Date.now()-172800000).toISOString()},
  // Energy
  { id: 'e1',  layer: 'energy',   lat: 57.7,  lng: 12.0,  title: 'Grid anomaly — Northern Europe',         severity: 'medium', timestamp: new Date(Date.now()-7200000).toISOString()  },
  { id: 'e2',  layer: 'energy',   lat: 24.7,  lng: 46.7,  title: 'Oil field monitoring — Riyadh region',   severity: 'low',    timestamp: new Date(Date.now()-21600000).toISOString() },
  { id: 'e3',  layer: 'energy',   lat: 52.2,  lng: 21.0,  title: 'Pipeline pressure event — Poland',       severity: 'medium', timestamp: new Date(Date.now()-3600000).toISOString()  },
]
