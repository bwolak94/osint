import { LAYER_CONFIGS, type LayerKey } from '../mapTypes'

interface LayerPanelProps {
  activeLayers: Set<LayerKey>
  onToggle: (key: LayerKey) => void
  eventCounts: Record<LayerKey, number>
}

export function LayerPanel({ activeLayers, onToggle, eventCounts }: LayerPanelProps) {
  return (
    <div
      className="absolute top-3 left-3 z-[1000] rounded-lg p-3 space-y-1.5"
      style={{ background: 'rgba(10,11,20,0.88)', border: '1px solid rgba(55,65,81,0.8)', backdropFilter: 'blur(8px)', minWidth: 190 }}
    >
      <div className="text-[10px] font-semibold uppercase tracking-widest mb-2" style={{ color: '#6b7280' }}>
        Layers
      </div>
      {LAYER_CONFIGS.map(({ key, label, color, emoji }) => {
        const active = activeLayers.has(key)
        const count = eventCounts[key] ?? 0
        return (
          <button
            key={key}
            onClick={() => onToggle(key)}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left transition-colors"
            style={{
              background: active ? `${color}18` : 'transparent',
              border: `1px solid ${active ? color + '40' : 'transparent'}`,
            }}
          >
            {/* Checkbox */}
            <span
              className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm"
              style={{ background: active ? color : 'transparent', border: `1.5px solid ${active ? color : '#4b5563'}` }}
            >
              {active && (
                <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                  <path d="M1 4l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </span>
            <span className="text-xs flex-1" style={{ color: active ? '#e5e7eb' : '#6b7280' }}>
              {emoji} {label}
            </span>
            {count > 0 && (
              <span
                className="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
                style={{ background: `${color}22`, color }}
              >
                {count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
