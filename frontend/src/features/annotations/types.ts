export type AnnotationSeverity = 'info' | 'warning' | 'critical'

export interface Annotation {
  id: string
  investigation_id: string
  target_id: string
  target_type: string
  content: string
  severity: AnnotationSeverity
  author: string
  created_at: string
  updated_at: string
}

export interface CreateAnnotationRequest {
  target_id: string
  target_type: string
  content: string
  severity: AnnotationSeverity
}

export interface UpdateAnnotationRequest {
  content?: string
  severity?: AnnotationSeverity
}

export type NotificationType = 'mention' | 'alert' | 'system'

export interface Notification {
  id: string
  type: NotificationType
  context: string
  investigation_id: string | null
  is_read: boolean
  created_at: string
}

export interface CreateMentionRequest {
  investigation_id: string
  mentioned_user_id: string
  context: string
  target_type: string
  target_id: string
}
