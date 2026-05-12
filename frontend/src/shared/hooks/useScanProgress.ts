import { useState, useEffect, useCallback } from 'react'

interface ScanProgressEvent {
  scan_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number // 0-100
  message: string
  scanner?: string
}

interface UseScanProgressOptions {
  scanId: string | null
  onComplete?: (result: ScanProgressEvent) => void
  onError?: (error: ScanProgressEvent) => void
}

export function useScanProgress({ scanId, onComplete, onError }: UseScanProgressOptions) {
  const [progress, setProgress] = useState<ScanProgressEvent | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  // Stable refs for callbacks to avoid re-opening SSE connections on callback identity changes
  const onCompleteCallback = useCallback(
    (result: ScanProgressEvent) => onComplete?.(result),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onComplete],
  )

  const onErrorCallback = useCallback(
    (error: ScanProgressEvent) => onError?.(error),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onError],
  )

  useEffect(() => {
    if (!scanId) return

    const url = `/api/v1/sse/scan/${scanId}`
    const es = new EventSource(url)

    es.onopen = () => setIsConnected(true)

    es.onmessage = (event: MessageEvent<string>) => {
      try {
        const data: ScanProgressEvent = JSON.parse(event.data)
        setProgress(data)
        if (data.status === 'completed') {
          onCompleteCallback(data)
          es.close()
        }
        if (data.status === 'failed') {
          onErrorCallback(data)
          es.close()
        }
      } catch {
        // Silently ignore malformed SSE payloads
      }
    }

    es.onerror = () => {
      setIsConnected(false)
      es.close()
    }

    return () => {
      es.close()
      setIsConnected(false)
    }
  }, [scanId, onCompleteCallback, onErrorCallback])

  return { progress, isConnected }
}
