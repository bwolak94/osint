import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { annotationsApi, notificationsApi } from './api'
import type { CreateAnnotationRequest, UpdateAnnotationRequest } from './types'

const ANNOTATIONS_KEY = 'annotations'
const NOTIFICATIONS_KEY = 'notifications'

export function useAnnotations(investigationId: string, targetId?: string) {
  return useQuery({
    queryKey: [ANNOTATIONS_KEY, investigationId, targetId],
    queryFn: () => annotationsApi.list(investigationId, targetId),
    enabled: Boolean(investigationId),
  })
}

export function useCreateAnnotation(investigationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: CreateAnnotationRequest) => annotationsApi.create(investigationId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ANNOTATIONS_KEY, investigationId] })
    },
  })
}

export function useUpdateAnnotation(investigationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ annotationId, body }: { annotationId: string; body: UpdateAnnotationRequest }) =>
      annotationsApi.update(annotationId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ANNOTATIONS_KEY, investigationId] })
    },
  })
}

export function useDeleteAnnotation(investigationId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (annotationId: string) => annotationsApi.delete(annotationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [ANNOTATIONS_KEY, investigationId] })
    },
  })
}

export function useNotifications() {
  return useQuery({
    queryKey: [NOTIFICATIONS_KEY],
    queryFn: () => notificationsApi.list(),
    refetchInterval: 30_000,
  })
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (notificationId: string) => notificationsApi.markRead(notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [NOTIFICATIONS_KEY] })
    },
  })
}

export function useMarkAllRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [NOTIFICATIONS_KEY] })
    },
  })
}
