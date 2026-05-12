export type WatchItemType = 'email' | 'phone' | 'username' | 'nip' | 'url' | 'ip' | 'domain'

export type WatchItemStatus = 'active' | 'paused' | 'error'

export type CronSchedule = '@daily' | '@hourly' | '@weekly'

export type NotificationChannel = 'email' | 'slack' | 'webhook'

export interface WatchItem {
  id: string
  label: string
  input_type: WatchItemType
  value: string
  cron_schedule: CronSchedule
  status: WatchItemStatus
  last_checked: string | null
  last_result_hash: string | null
  alert_on_change: boolean
  notification_channels: NotificationChannel[]
  created_at: string
  investigation_id: string | null
}

export interface CreateWatchItemRequest {
  label: string
  input_type: WatchItemType
  value: string
  cron_schedule: CronSchedule
  status: WatchItemStatus
  alert_on_change: boolean
  notification_channels: NotificationChannel[]
  investigation_id: string | null
}

export interface WatchlistStats {
  total: number
  active: number
  paused: number
  triggered_today: number
}
