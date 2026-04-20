export interface DocMetadata {
  id: string
  filename: string
  file_hash: string
  file_size: number
  mime_type: string
  doc_format: string | null
  author: string | null
  creator_tool: string | null
  company: string | null
  last_modified_by: string | null
  created_at_doc: string | null
  modified_at_doc: string | null
  revision_count: number | null
  has_macros: boolean
  has_hidden_content: boolean
  has_tracked_changes: boolean
  gps_lat: number | null
  gps_lon: number | null
  raw_metadata: Record<string, string | number | null>
  embedded_files: string[]
  created_at: string
}

export interface DocMetadataListResponse {
  items: DocMetadata[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
