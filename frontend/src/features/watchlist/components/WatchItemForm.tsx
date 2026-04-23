import { useState, useCallback } from 'react'
import { X, Eye } from 'lucide-react'
import type { WatchItem, WatchItemType, CronSchedule, NotificationChannel, CreateWatchItemRequest } from '../types'

interface Props {
  initial?: WatchItem
  onClose: () => void
  onSubmit: (data: CreateWatchItemRequest) => void
  isPending: boolean
}

const INPUT_TYPE_OPTIONS: { value: WatchItemType; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'username', label: 'Username' },
  { value: 'nip', label: 'NIP' },
  { value: 'url', label: 'URL' },
  { value: 'ip', label: 'IP' },
  { value: 'domain', label: 'Domain' },
]

const SCHEDULE_OPTIONS: { value: CronSchedule; label: string }[] = [
  { value: '@hourly', label: 'Hourly' },
  { value: '@daily', label: 'Daily' },
  { value: '@weekly', label: 'Weekly' },
]

const CHANNEL_OPTIONS: { value: NotificationChannel; label: string }[] = [
  { value: 'email', label: 'Email' },
  { value: 'slack', label: 'Slack' },
  { value: 'webhook', label: 'Webhook' },
]

export function WatchItemForm({ initial, onClose, onSubmit, isPending }: Props) {
  const [label, setLabel] = useState(initial?.label ?? '')
  const [inputType, setInputType] = useState<WatchItemType>(initial?.input_type ?? 'domain')
  const [value, setValue] = useState(initial?.value ?? '')
  const [cronSchedule, setCronSchedule] = useState<CronSchedule>(initial?.cron_schedule ?? '@daily')
  const [alertOnChange, setAlertOnChange] = useState(initial?.alert_on_change ?? true)
  const [notificationChannels, setNotificationChannels] = useState<NotificationChannel[]>(
    initial?.notification_channels ?? ['email'],
  )
  const [investigationId, setInvestigationId] = useState(initial?.investigation_id ?? '')
  const [error, setError] = useState('')

  const toggleChannel = useCallback((channel: NotificationChannel) => {
    setNotificationChannels((prev) =>
      prev.includes(channel) ? prev.filter((c) => c !== channel) : [...prev, channel],
    )
  }, [])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (!label.trim()) { setError('Label is required'); return }
      if (!value.trim()) { setError('Value to monitor is required'); return }
      setError('')
      onSubmit({
        label: label.trim(),
        input_type: inputType,
        value: value.trim(),
        cron_schedule: cronSchedule,
        status: initial?.status ?? 'active',
        alert_on_change: alertOnChange,
        notification_channels: notificationChannels,
        investigation_id: investigationId.trim() || null,
      })
    },
    [label, inputType, value, cronSchedule, alertOnChange, notificationChannels, investigationId, initial, onSubmit],
  )

  const inputClass =
    'w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-brand-500'
  const inputStyle = {
    background: 'var(--bg-elevated)',
    borderColor: 'var(--border-default)',
    color: 'var(--text-primary)',
  }
  const labelClass = 'block text-xs font-medium mb-1.5'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border p-6 shadow-2xl"
        style={{ background: 'var(--bg-surface)', borderColor: 'var(--border-subtle)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <Eye className="h-5 w-5" style={{ color: 'var(--brand-500)' }} />
            <h2 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
              {initial ? 'Edit Watch Item' : 'Add Watch Item'}
            </h2>
          </div>
          <button onClick={onClose} className="rounded p-1 hover:bg-white/5">
            <X className="h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Label */}
          <div>
            <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
              Label
            </label>
            <input
              type="text"
              placeholder="e.g. Company CEO email"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={inputClass}
              style={inputStyle}
              autoFocus
            />
          </div>

          {/* Type + Schedule row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
                Type
              </label>
              <select
                value={inputType}
                onChange={(e) => setInputType(e.target.value as WatchItemType)}
                className={inputClass}
                style={inputStyle}
              >
                {INPUT_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
                Schedule
              </label>
              <select
                value={cronSchedule}
                onChange={(e) => setCronSchedule(e.target.value as CronSchedule)}
                className={inputClass}
                style={inputStyle}
              >
                {SCHEDULE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Value */}
          <div>
            <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
              Value to Monitor
            </label>
            <input
              type="text"
              placeholder={
                inputType === 'email'
                  ? 'user@example.com'
                  : inputType === 'ip'
                    ? '192.168.1.1'
                    : inputType === 'domain'
                      ? 'example.com'
                      : inputType === 'url'
                        ? 'https://example.com/page'
                        : inputType === 'phone'
                          ? '+48123456789'
                          : inputType === 'nip'
                            ? '1234567890'
                            : 'value to watch'
              }
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className={inputClass}
              style={{ ...inputStyle, fontFamily: 'monospace' }}
            />
          </div>

          {/* Notification channels */}
          <div>
            <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
              Notification Channels
            </label>
            <div className="flex items-center gap-4">
              {CHANNEL_OPTIONS.map((opt) => (
                <label
                  key={opt.value}
                  className="flex items-center gap-2 cursor-pointer select-none text-sm"
                  style={{ color: 'var(--text-primary)' }}
                >
                  <input
                    type="checkbox"
                    checked={notificationChannels.includes(opt.value)}
                    onChange={() => toggleChannel(opt.value)}
                    className="h-4 w-4 rounded accent-brand-500"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Alert on change */}
          <div>
            <label
              className="flex items-center gap-2 cursor-pointer select-none text-sm"
              style={{ color: 'var(--text-primary)' }}
            >
              <input
                type="checkbox"
                checked={alertOnChange}
                onChange={(e) => setAlertOnChange(e.target.checked)}
                className="h-4 w-4 rounded accent-brand-500"
              />
              Alert when result changes
            </label>
            <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
              Triggers a notification when the scan result differs from the previous run
            </p>
          </div>

          {/* Investigation ID (optional) */}
          <div>
            <label className={labelClass} style={{ color: 'var(--text-secondary)' }}>
              Investigation ID{' '}
              <span className="font-normal" style={{ color: 'var(--text-tertiary)' }}>
                (optional)
              </span>
            </label>
            <input
              type="text"
              placeholder="Link to an existing investigation UUID"
              value={investigationId}
              onChange={(e) => setInvestigationId(e.target.value)}
              className={inputClass}
              style={inputStyle}
            />
          </div>

          {/* Error */}
          {error && (
            <p className="text-xs" style={{ color: 'var(--danger-500)' }}>
              {error}
            </p>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{ background: 'var(--brand-500)', color: 'white' }}
            >
              {isPending ? 'Saving…' : initial ? 'Save Changes' : 'Add Watch Item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
