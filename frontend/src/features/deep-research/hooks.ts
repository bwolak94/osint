import { useState, useCallback, useRef } from 'react'
import { toast } from '@/shared/components/Toast'
import type { DeepResearchRequest, DeepResearchResult } from './types'

export interface ModuleProgress {
  module: string
  status: 'pending' | 'running' | 'done' | 'error'
  message?: string | undefined
}

export interface UseDeepResearchReturn {
  run: (req: DeepResearchRequest) => void
  cancel: () => void
  isPending: boolean
  result: DeepResearchResult | null
  progress: ModuleProgress[]
  error: string | null
}

/** Build the SSE query string from a request object. */
function toQueryString(req: DeepResearchRequest): string {
  const params = new URLSearchParams()
  if (req.first_name) params.set('first_name', req.first_name)
  if (req.last_name) params.set('last_name', req.last_name)
  if (req.email) params.set('email', req.email)
  if (req.username) params.set('username', req.username)
  if (req.phone) params.set('phone', req.phone)
  if (req.nip) params.set('nip', req.nip)
  if (req.company_name) params.set('company_name', req.company_name)
  return params.toString()
}

export function useDeepResearch(): UseDeepResearchReturn {
  const [isPending, setIsPending] = useState(false)
  const [result, setResult] = useState<DeepResearchResult | null>(null)
  const [progress, setProgress] = useState<ModuleProgress[]>([])
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const cancel = useCallback(() => {
    if (esRef.current) {
      esRef.current.close()
      esRef.current = null
    }
    setIsPending(false)
  }, [])

  const run = useCallback((req: DeepResearchRequest) => {
    // Close any existing stream
    if (esRef.current) {
      esRef.current.close()
    }
    setResult(null)
    setError(null)
    setProgress([])
    setIsPending(true)

    const qs = toQueryString(req)
    const es = new EventSource(`/api/v1/deep-research/stream?${qs}`)
    esRef.current = es

    es.addEventListener('module', (e: MessageEvent<string>) => {
      try {
        const data = JSON.parse(e.data) as { module: string; status: string; message?: string }
        setProgress((prev) => {
          const idx = prev.findIndex((p) => p.module === data.module)
          const entry: ModuleProgress = {
            module: data.module,
            status: data.status as ModuleProgress['status'],
            message: data.message,
          }
          if (idx >= 0) {
            const next = [...prev]
            next[idx] = entry
            return next
          }
          return [...prev, entry]
        })
      } catch { /* ignore */ }
    })

    es.addEventListener('complete', (e: MessageEvent<string>) => {
      try {
        const data = JSON.parse(e.data) as DeepResearchResult
        setResult(data)
        // Mark all modules as done
        setProgress((prev) => prev.map((p) => ({ ...p, status: 'done' as const })))
      } catch {
        toast.error('Failed to parse research results')
      }
      es.close()
      esRef.current = null
      setIsPending(false)
    })

    es.addEventListener('error', (e: MessageEvent<string>) => {
      try {
        const data = JSON.parse(e.data) as { message: string }
        setError(data.message)
        toast.error(data.message)
      } catch {
        // Generic SSE error (connection lost etc.)
        toast.error('Research stream disconnected')
      }
      es.close()
      esRef.current = null
      setIsPending(false)
    })

    // Native onerror fires on connection failure
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setIsPending(false)
      }
    }
  }, [])

  return { run, cancel, isPending, result, progress, error }
}
