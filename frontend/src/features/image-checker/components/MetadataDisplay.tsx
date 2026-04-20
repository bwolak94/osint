import { useState } from 'react'
import { MapPin, Camera, Calendar, FileImage, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { Card, CardHeader, CardBody } from '@/shared/components/Card'
import { Button } from '@/shared/components/Button'
import { Badge } from '@/shared/components/Badge'
import type { ImageCheck } from '../types'

interface Props {
  check: ImageCheck
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

function formatMetaKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

interface InfoRowProps {
  label: string
  value: string | number | null | undefined
}

function InfoRow({ label, value }: InfoRowProps) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <span className="shrink-0 text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
        {label}
      </span>
      <span
        className="text-right text-xs font-medium"
        style={{ color: 'var(--text-primary)' }}
      >
        {String(value)}
      </span>
    </div>
  )
}

export function MetadataDisplay({ check }: Props) {
  const [exifExpanded, setExifExpanded] = useState(false)

  const cameraName = [check.camera_make, check.camera_model].filter(Boolean).join(' ') || null

  const imageWidth = check.metadata['Image Width'] ?? check.metadata['image_width'] ?? null
  const imageHeight = check.metadata['Image Height'] ?? check.metadata['image_height'] ?? null
  const dimensions =
    imageWidth && imageHeight ? `${imageWidth} × ${imageHeight}` : null

  const filteredMetadata = Object.entries(check.metadata).filter(
    ([, v]) => v !== null && v !== undefined && v !== '',
  )

  return (
    <div className="space-y-4">
      {/* Top row: Image Info + GPS */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Image Info */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileImage className="h-4 w-4" style={{ color: 'var(--brand-500)' }} />
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Image Info
              </h3>
            </div>
          </CardHeader>
          <CardBody>
            <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
              <InfoRow label="Filename" value={check.filename} />
              <InfoRow label="File Size" value={formatFileSize(check.file_size)} />
              <InfoRow label="MIME Type" value={check.mime_type} />
              {dimensions && <InfoRow label="Dimensions" value={dimensions} />}
              {cameraName && (
                <div className="flex items-start justify-between gap-4 py-2">
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Camera className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
                      Camera
                    </span>
                  </div>
                  <span className="text-right text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                    {cameraName}
                  </span>
                </div>
              )}
              {check.taken_at && (
                <div className="flex items-start justify-between gap-4 py-2">
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Calendar className="h-3.5 w-3.5" style={{ color: 'var(--text-tertiary)' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>
                      Taken At
                    </span>
                  </div>
                  <span className="text-right text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                    {formatDate(check.taken_at)}
                  </span>
                </div>
              )}
            </div>
          </CardBody>
        </Card>

        {/* GPS Location */}
        {check.gps_data ? (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" style={{ color: 'var(--success-500)' }} />
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  GPS Location
                </h3>
                <Badge variant="success" size="sm">Found</Badge>
              </div>
            </CardHeader>
            <CardBody className="space-y-4">
              <div className="divide-y" style={{ borderColor: 'var(--border-subtle)' }}>
                <InfoRow
                  label="Latitude"
                  value={check.gps_data.latitude.toFixed(6)}
                />
                <InfoRow
                  label="Longitude"
                  value={check.gps_data.longitude.toFixed(6)}
                />
                {check.gps_data.altitude !== null && (
                  <InfoRow
                    label="Altitude"
                    value={`${check.gps_data.altitude.toFixed(1)} m`}
                  />
                )}
                {check.gps_data.gps_timestamp && (
                  <InfoRow
                    label="GPS Timestamp"
                    value={check.gps_data.gps_timestamp}
                  />
                )}
              </div>

              <a
                href={check.gps_data.maps_url}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <Button variant="primary" className="w-full" size="md">
                  <MapPin className="h-4 w-4" />
                  Open in Google Maps
                  <ExternalLink className="h-3.5 w-3.5 opacity-70" />
                </Button>
              </a>
            </CardBody>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                  GPS Location
                </h3>
                <Badge variant="neutral" size="sm">Not found</Badge>
              </div>
            </CardHeader>
            <CardBody>
              <div className="flex flex-col items-center justify-center py-8 text-center gap-3">
                <div
                  className="flex h-10 w-10 items-center justify-center rounded-full"
                  style={{ background: 'var(--bg-elevated)' }}
                >
                  <MapPin className="h-5 w-5" style={{ color: 'var(--text-tertiary)' }} />
                </div>
                <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  No GPS data found in this image
                </p>
              </div>
            </CardBody>
          </Card>
        )}
      </div>

      {/* EXIF Metadata — collapsible */}
      <Card>
        <CardHeader>
          <button
            onClick={() => setExifExpanded((prev) => !prev)}
            className="flex w-full items-center justify-between focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
            aria-expanded={exifExpanded}
            aria-controls="exif-metadata-table"
          >
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                EXIF Metadata
              </h3>
              <Badge variant="neutral" size="sm">{filteredMetadata.length} tags</Badge>
            </div>
            {exifExpanded ? (
              <ChevronUp className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            ) : (
              <ChevronDown className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            )}
          </button>
        </CardHeader>

        {exifExpanded && (
          <div id="exif-metadata-table">
            {filteredMetadata.length === 0 ? (
              <CardBody>
                <p className="text-sm text-center py-4" style={{ color: 'var(--text-tertiary)' }}>
                  No EXIF metadata available
                </p>
              </CardBody>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr
                      className="border-b"
                      style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-tertiary)' }}
                    >
                      <th className="px-5 py-2.5 text-left font-medium">Tag</th>
                      <th className="px-5 py-2.5 text-left font-medium">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMetadata.map(([key, value]) => (
                      <tr
                        key={key}
                        className="border-b transition-colors hover:bg-bg-overlay"
                        style={{ borderColor: 'var(--border-subtle)' }}
                      >
                        <td
                          className="px-5 py-2 font-medium"
                          style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}
                        >
                          {formatMetaKey(key)}
                        </td>
                        <td
                          className="px-5 py-2 font-mono"
                          style={{ color: 'var(--text-primary)', wordBreak: 'break-all' }}
                        >
                          {String(value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
