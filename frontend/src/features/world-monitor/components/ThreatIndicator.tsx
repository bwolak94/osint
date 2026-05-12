interface ThreatIndicatorProps {
  level: number // 1-5 (1 = DEFCON 1 critical, 5 = peacetime)
}

const LEVELS = [
  { level: 1, label: 'DEFCON 1', color: '#ef4444', bg: '#ef444420', desc: 'COCKED PISTOL' },
  { level: 2, label: 'DEFCON 2', color: '#f97316', bg: '#f9731620', desc: 'FAST PACE' },
  { level: 3, label: 'DEFCON 3', color: '#eab308', bg: '#eab30820', desc: 'ROUND HOUSE' },
  { level: 4, label: 'DEFCON 4', color: '#3b82f6', bg: '#3b82f620', desc: 'DOUBLE TAKE' },
  { level: 5, label: 'DEFCON 5', color: '#10b981', bg: '#10b98120', desc: 'FADE OUT' },
]

export function ThreatIndicator({ level }: ThreatIndicatorProps) {
  const cfg = LEVELS.find((l) => l.level === level) ?? LEVELS[4]
  return (
    <div
      className="flex items-center gap-2 rounded px-2.5 py-1.5"
      style={{ background: cfg.bg, border: `1px solid ${cfg.color}40` }}
      title={cfg.desc}
    >
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: cfg.color, boxShadow: `0 0 6px ${cfg.color}` }}
      />
      <span className="text-xs font-bold tracking-wider" style={{ color: cfg.color }}>
        {cfg.label}
      </span>
    </div>
  )
}
