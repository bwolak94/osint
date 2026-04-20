export interface BucketResult {
  name: string
  provider: string
  url: string
  is_public: boolean
  file_count: number
  sample_files: string[]
  has_sensitive_files: boolean
  sensitive_file_count: number
}

export interface CloudExposureScan {
  id: string
  target: string
  total_buckets: number
  public_buckets: number
  sensitive_findings: number
  buckets: BucketResult[]
  created_at: string
}

export interface CloudExposureListResponse {
  items: CloudExposureScan[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
