import { useState, useCallback } from 'react'
import { AlertCircle } from 'lucide-react'
import { Button } from '@/shared/components/Button'
import { useAnalyzeEmailHeaders } from '../hooks'
import type { EmailHeaderCheck } from '../types'

interface Props {
  onSuccess: (result: EmailHeaderCheck) => void
}

const PLACEHOLDER = `Received: from mail.example.com ([192.0.2.1]) by mx.gmail.com with ESMTP; Mon, 19 Apr 2026 10:00:00 +0000
Authentication-Results: mx.gmail.com; spf=pass; dkim=pass; dmarc=pass
From: sender@example.com
To: recipient@gmail.com
Subject: Test email
Date: Mon, 19 Apr 2026 10:00:00 +0000
Message-ID: <unique-id@example.com>`

export function HeaderInputForm({ onSuccess }: Props) {
  const [rawHeaders, setRawHeaders] = useState('')
  const analyzeMutation = useAnalyzeEmailHeaders()

  const handleSubmit = useCallback(() => {
    if (!rawHeaders.trim()) return
    analyzeMutation.mutate(rawHeaders, { onSuccess })
  }, [rawHeaders, analyzeMutation, onSuccess])

  const errorMessage = analyzeMutation.error?.message

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="raw-headers" className="mb-2 block text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Paste raw email headers
        </label>
        <textarea
          id="raw-headers"
          value={rawHeaders}
          onChange={(e) => setRawHeaders(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={12}
          className="w-full rounded-lg border bg-transparent px-3 py-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          style={{ borderColor: 'var(--border-default)', color: 'var(--text-primary)', resize: 'vertical' }}
          aria-label="Raw email headers input"
        />
      </div>

      {errorMessage && (
        <div className="flex items-start gap-2 rounded-lg border px-3 py-2 text-sm" role="alert" style={{ background: 'var(--danger-900)', borderColor: 'var(--danger-500)', color: 'var(--danger-500)' }}>
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <Button onClick={handleSubmit} disabled={!rawHeaders.trim()} loading={analyzeMutation.isPending} className="w-full" size="lg">
        Analyze Headers
      </Button>
    </div>
  )
}
