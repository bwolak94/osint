/**
 * WorldMap — Leaflet-based dark interactive map.
 * Uses CartoDB Dark Matter tiles (free, no API key).
 * Layer markers are generated from mock data seeded by RSS item counts.
 */
import { useEffect, useRef } from 'react'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import type { LayerKey, MapEvent } from '../mapTypes'
import { REGION_VIEWS } from '../mapTypes'

// Fix default icon paths broken by Vite bundling
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const LAYER_COLORS: Record<LayerKey, string> = {
  conflict: '#ef4444',
  intel: '#f97316',
  military: '#3b82f6',
  nuclear: '#a855f7',
  cyber: '#10b981',
  crisis: '#eab308',
  energy: '#6366f1',
  disaster: '#fb923c',
}

function makeCircleMarker(color: string, pulseRing = false) {
  return L.divIcon({
    className: '',
    html: `
      <div style="position:relative;width:12px;height:12px;">
        ${pulseRing ? `<div style="position:absolute;inset:-4px;border-radius:50%;border:2px solid ${color};opacity:.4;animation:wm-pulse 2s infinite;"></div>` : ''}
        <div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid rgba(255,255,255,.25);box-shadow:0 0 6px ${color}88;"></div>
      </div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  })
}

interface WorldMapProps {
  events: MapEvent[]
  activeLayers: Set<LayerKey>
  timeRange: string
  region?: string
}

export function WorldMap({ events, activeLayers, timeRange, region = 'Global' }: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerGroupRef = useRef<L.LayerGroup | null>(null)

  // Inject pulse keyframe once
  useEffect(() => {
    if (document.getElementById('wm-pulse-style')) return
    const style = document.createElement('style')
    style.id = 'wm-pulse-style'
    style.textContent = `@keyframes wm-pulse{0%{transform:scale(1);opacity:.4}50%{transform:scale(1.8);opacity:.1}100%{transform:scale(1);opacity:.4}}`
    document.head.appendChild(style)
  }, [])

  // Init map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = L.map(containerRef.current, {
      center: [20, 10],
      zoom: 2,
      minZoom: 2,
      maxZoom: 10,
      zoomControl: false,
      attributionControl: false,
    })

    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { subdomains: 'abcd', maxZoom: 19 }
    ).addTo(map)

    L.control.attribution({ prefix: false, position: 'bottomright' })
      .addAttribution('<span style="color:#4b5563;font-size:9px">© CartoDB © OSM</span>')
      .addTo(map)

    L.control.zoom({ position: 'topright' }).addTo(map)

    layerGroupRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Fly to region when selector changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const view = REGION_VIEWS[region] ?? REGION_VIEWS['Global']
    map.flyTo(view.center, view.zoom, { duration: 1.2 })
  }, [region])

  // Update markers when events/filters change
  useEffect(() => {
    const group = layerGroupRef.current
    if (!group) return
    group.clearLayers()

    const now = Date.now()
    const hoursMap: Record<string, number> = { '1h': 1, '6h': 6, '24h': 24, '48h': 48, '7d': 168, all: 99999 }
    const cutoffHours = hoursMap[timeRange] ?? 168
    const cutoffMs = cutoffHours * 3600 * 1000

    events
      .filter((e) => activeLayers.has(e.layer))
      .filter((e) => now - new Date(e.timestamp).getTime() < cutoffMs)
      .forEach((ev) => {
        const color = LAYER_COLORS[ev.layer]
        const marker = L.marker([ev.lat, ev.lng], {
          icon: makeCircleMarker(color, ev.severity === 'high'),
          title: ev.title,
        })
        const source = (ev as MapEvent & { source?: string }).source
        marker.bindTooltip(
          `<div style="background:#1a1f2e;border:1px solid #374151;padding:6px 10px;border-radius:6px;font-size:11px;color:#e5e7eb;max-width:240px;">
            <div style="color:${color};font-weight:600;margin-bottom:2px;">${ev.layer.toUpperCase()}${source ? ` · ${source}` : ''}</div>
            <div>${ev.title}</div>
          </div>`,
          { className: 'wm-tooltip', opacity: 1 }
        )
        group.addLayer(marker)
      })
  }, [events, activeLayers, timeRange])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
      {/* Suppress Leaflet default tooltip styles */}
      <style>{`.wm-tooltip .leaflet-tooltip{background:transparent;border:none;box-shadow:none;padding:0}`}</style>
    </div>
  )
}
