import { useState, useCallback, useRef, useEffect } from 'react'
import { Bell, MessageSquare, AlertTriangle, Info } from 'lucide-react'
import { useNotifications, useMarkNotificationRead, useMarkAllRead } from '../hooks'
import type { Notification, NotificationType } from '../types'

function formatRelativeTime(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime()
  const diffMins = Math.floor(diffMs / 60_000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

const TYPE_ICON: Record<NotificationType, typeof Bell> = {
  mention: MessageSquare,
  alert: AlertTriangle,
  system: Info,
}

const TYPE_COLOR: Record<NotificationType, string> = {
  mention: 'var(--brand-500)',
  alert: 'var(--warning-500)',
  system: 'var(--text-tertiary)',
}

interface NotificationItemProps {
  notification: Notification
  onMarkRead: (id: string) => void
  isMarkingRead: boolean
}

function NotificationItem({ notification, onMarkRead, isMarkingRead }: NotificationItemProps) {
  const Icon = TYPE_ICON[notification.type]
  const color = TYPE_COLOR[notification.type]

  const handleClick = useCallback(() => {
    if (!notification.is_read) {
      onMarkRead(notification.id)
    }
  }, [notification.id, notification.is_read, onMarkRead])

  return (
    <button
      onClick={handleClick}
      disabled={isMarkingRead || notification.is_read}
      className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors disabled:cursor-default"
      style={{
        background: notification.is_read ? 'transparent' : 'var(--bg-elevated)',
        borderBottom: '1px solid var(--border-subtle)',
        opacity: notification.is_read ? 0.6 : 1,
      }}
    >
      <div className="mt-0.5 shrink-0">
        <Icon className="h-4 w-4" style={{ color }} />
      </div>

      <div className="min-w-0 flex-1">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-primary)' }}>
          {notification.context}
        </p>
        <div className="mt-1 flex items-center gap-2">
          {notification.investigation_id && (
            <a
              href={`/investigations/${notification.investigation_id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-xs underline-offset-2 hover:underline"
              style={{ color: 'var(--brand-500)' }}
            >
              View investigation
            </a>
          )}
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {formatRelativeTime(notification.created_at)}
          </span>
        </div>
      </div>

      {!notification.is_read && (
        <span
          className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
          style={{ background: 'var(--brand-500)' }}
        />
      )}
    </button>
  )
}

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)

  const { data: notifications = [], isLoading } = useNotifications()
  const markReadMutation = useMarkNotificationRead()
  const markAllReadMutation = useMarkAllRead()

  const unreadCount = notifications.filter((n) => !n.is_read).length

  const handleToggle = useCallback(() => setIsOpen((prev) => !prev), [])

  const handleMarkRead = useCallback(
    (id: string) => {
      markReadMutation.mutate(id)
    },
    [markReadMutation],
  )

  const handleMarkAllRead = useCallback(() => {
    markAllReadMutation.mutate()
  }, [markAllReadMutation])

  // Close panel on outside click
  useEffect(() => {
    if (!isOpen) return
    function onPointerDown(e: PointerEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [isOpen])

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={handleToggle}
        className="relative flex h-8 w-8 items-center justify-center rounded-md transition-colors"
        style={{
          background: isOpen ? 'var(--bg-elevated)' : 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid transparent',
          ...(isOpen ? { borderColor: 'var(--border-subtle)' } : {}),
        }}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
        aria-expanded={isOpen}
        aria-controls="notification-panel"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span
            className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold"
            style={{ background: 'var(--danger-400)', color: '#fff' }}
            aria-hidden="true"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          id="notification-panel"
          ref={panelRef}
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 top-full z-50 mt-2 flex flex-col overflow-hidden rounded-lg shadow-xl"
          style={{
            width: '360px',
            maxHeight: '480px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          {/* Panel header */}
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: '1px solid var(--border-subtle)' }}
          >
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Notifications
              {unreadCount > 0 && (
                <span
                  className="ml-2 rounded-full px-1.5 py-0.5 text-xs font-medium"
                  style={{ background: 'var(--brand-500)', color: '#fff' }}
                >
                  {unreadCount}
                </span>
              )}
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={markAllReadMutation.isPending}
                className="text-xs transition-colors hover:underline disabled:opacity-50"
                style={{ color: 'var(--brand-500)' }}
              >
                {markAllReadMutation.isPending ? 'Marking…' : 'Mark all read'}
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="overflow-y-auto" style={{ flex: 1 }}>
            {isLoading && (
              <p className="py-8 text-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
                Loading…
              </p>
            )}

            {!isLoading && notifications.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-10">
                <Bell className="h-8 w-8" style={{ color: 'var(--text-tertiary)' }} />
                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  You're all caught up
                </p>
              </div>
            )}

            {notifications.map((notification) => (
              <NotificationItem
                key={notification.id}
                notification={notification}
                onMarkRead={handleMarkRead}
                isMarkingRead={markReadMutation.isPending}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
