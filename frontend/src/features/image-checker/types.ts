export interface GPSData {
  latitude: number
  longitude: number
  altitude: number | null
  gps_timestamp: string | null
  maps_url: string
}

export interface ImageCheck {
  id: string
  filename: string
  file_hash: string
  file_size: number
  mime_type: string
  metadata: Record<string, string | number | null>
  gps_data: GPSData | null
  camera_make: string | null
  camera_model: string | null
  taken_at: string | null
  created_at: string
}

export interface ImageCheckListResponse {
  items: ImageCheck[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
