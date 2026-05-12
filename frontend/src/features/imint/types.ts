export interface ModuleResultData {
  found: boolean
  data?: Record<string, unknown>
  error?: string | null
  status?: string
  skipped?: boolean
  reason?: string
}

export interface ImintScan {
  id: string
  target: string
  target_type: 'image_url' | 'coordinates' | 'url'
  modules_run: string[]
  results: Record<string, ModuleResultData>
  created_at: string
}

export interface ImintListResponse {
  items: ImintScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ImintRequest {
  target: string
  modules?: string[]
}

export interface ModuleGroup {
  key: string
  label: string
  targetType: 'image_url' | 'coordinates' | 'any'
  modules: string[]
}

export const IMAGE_MODULE_GROUPS: ModuleGroup[] = [
  {
    key: 'metadata',
    label: 'Image Metadata',
    targetType: 'image_url',
    modules: ['exif_deep_extractor', 'forensic_image_auditor', 'perspective_distorter', 'neural_image_upscaler'],
  },
  {
    key: 'ai_analysis',
    label: 'AI & Visual Analysis',
    targetType: 'image_url',
    modules: ['deepfake_detector', 'visual_landmark_match', 'license_plate_decoder'],
  },
]

export const COORDINATES_MODULE_GROUPS: ModuleGroup[] = [
  {
    key: 'satellite',
    label: 'Satellite & Maps',
    targetType: 'coordinates',
    modules: ['satellite_delta_mapper', 'street_view_pivot', 'historical_map_overlay'],
  },
  {
    key: 'solar',
    label: 'Solar & Environmental',
    targetType: 'coordinates',
    modules: ['chronolocator', 'weather_correlation', 'vegetation_soil_mapper', 'building_height_estimator'],
  },
  {
    key: 'tracking',
    label: 'Asset Tracking',
    targetType: 'coordinates',
    modules: ['adsb_tracker', 'maritime_tracker', 'webcam_finder'],
  },
  {
    key: 'social_geo',
    label: 'Social & WiFi',
    targetType: 'coordinates',
    modules: ['social_media_geofence', 'public_wifi_mapper', 'geolocation_challenge'],
  },
]

export const MODULE_LABELS: Record<string, string> = {
  // Image modules
  exif_deep_extractor: 'EXIF Deep Extractor',
  forensic_image_auditor: 'Forensic Image Auditor (ELA)',
  deepfake_detector: 'Deepfake Detector',
  visual_landmark_match: 'Visual Landmark Match',
  license_plate_decoder: 'License Plate Decoder',
  perspective_distorter: 'Perspective Distorter',
  neural_image_upscaler: 'Neural Image Upscaler',
  // Coordinates modules
  satellite_delta_mapper: 'Satellite Delta Mapper',
  chronolocator: 'Chronolocator (Sun)',
  weather_correlation: 'Weather Correlation',
  webcam_finder: 'Webcam Finder',
  adsb_tracker: 'Aircraft Tracker (ADS-B)',
  maritime_tracker: 'Maritime Tracker (AIS)',
  geolocation_challenge: 'Geolocation Challenge',
  street_view_pivot: 'Street View Pivot',
  vegetation_soil_mapper: 'Vegetation/Soil Mapper',
  building_height_estimator: 'Building Height Estimator',
  social_media_geofence: 'Social Media Geofence',
  public_wifi_mapper: 'Public WiFi Mapper',
  historical_map_overlay: 'Historical Map Overlay',
}
