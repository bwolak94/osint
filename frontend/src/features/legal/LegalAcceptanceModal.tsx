import { useState } from 'react'
import { Shield, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react'
import { apiClient } from '@/shared/api/client'
import { useAuthStore } from '@/features/auth/store'

interface LegalAcceptanceModalProps {
  onAccepted: () => void
}

export function LegalAcceptanceModal({ onAccepted }: LegalAcceptanceModalProps) {
  const [checked, setChecked] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const setAuth = useAuthStore((s) => s.setAuth)
  const user = useAuthStore((s) => s.user)
  const accessToken = useAuthStore((s) => s.accessToken)

  const handleAccept = async () => {
    if (!checked || loading) return
    setLoading(true)
    setError(null)
    try {
      await apiClient.post('/api/v1/auth/accept-tos')
      // Update user in store so Layout won't show modal again
      if (user && accessToken) {
        setAuth({ ...user, tos_accepted_at: new Date().toISOString() }, accessToken)
      }
      onAccepted()
    } catch {
      setError('Failed to record acceptance. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="w-full max-w-lg rounded-2xl p-8 space-y-6"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)' }}
      >
        {/* Header */}
        <div className="flex items-start gap-4">
          <div
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl"
            style={{ background: 'var(--danger-900)' }}
          >
            <Shield className="h-6 w-6" style={{ color: 'var(--danger-400)' }} />
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Terms of Use &amp; Legal Notice
            </h2>
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-secondary)' }}>
              Required before accessing any security scanning features
            </p>
          </div>
        </div>

        {/* Warning banner */}
        <div
          className="flex gap-3 rounded-lg px-4 py-3 text-sm"
          style={{ background: 'var(--warning-900)', border: '1px solid var(--warning-600)' }}
        >
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" style={{ color: 'var(--warning-400)' }} />
          <p style={{ color: 'var(--warning-300)' }}>
            This platform provides offensive security and OSINT tools. Unauthorized use may constitute a criminal offence.
          </p>
        </div>

        {/* Terms content */}
        <div
          className="rounded-lg p-4 space-y-3 text-sm overflow-y-auto max-h-52"
          style={{ background: 'var(--bg-overlay)', border: '1px solid var(--border-subtle)' }}
        >
          <p style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Art. 269b KK (Polish Criminal Code)</strong> — Possession and use of hacking tools against systems you do not own or have no explicit written authorization to test is a criminal offence punishable by up to 2 years imprisonment.
          </p>
          <p style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>EU Dual-Use Regulation 2021/821</strong> — Penetration testing tools are classified as dual-use items. Export and use is subject to end-use controls. You confirm you are not subject to any export or sanctions restrictions.
          </p>
          <p style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Scope of Use</strong> — You may only use this platform against systems and networks for which you hold valid written authorization (Rules of Engagement). All scans are logged with timestamps, source IP, and a tamper-evident audit trail.
          </p>
          <p style={{ color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>No Warranty</strong> — This platform is provided for authorized security assessment purposes only. The operators accept no liability for misuse or unauthorized actions performed by users.
          </p>
        </div>

        {/* Checkbox */}
        <label className="flex items-start gap-3 cursor-pointer group">
          <div
            className="relative mt-0.5 h-5 w-5 shrink-0 rounded border-2 flex items-center justify-center transition-colors"
            style={{
              borderColor: checked ? 'var(--brand-500)' : 'var(--border-default)',
              background: checked ? 'var(--brand-500)' : 'transparent',
            }}
            onClick={() => setChecked((v) => !v)}
          >
            {checked && <CheckCircle2 className="h-3.5 w-3.5 text-white" />}
          </div>
          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            I confirm that I have read and understood the above terms. I have written authorization for all systems I intend to test and accept full legal responsibility for my actions.
          </span>
        </label>

        {error && (
          <p className="text-sm" style={{ color: 'var(--danger-400)' }}>{error}</p>
        )}

        {/* Accept button */}
        <button
          onClick={handleAccept}
          disabled={!checked || loading}
          className="w-full rounded-lg py-3 text-sm font-semibold transition-opacity disabled:opacity-40"
          style={{ background: 'var(--brand-500)', color: '#fff' }}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Recording acceptance…
            </span>
          ) : (
            'I Accept — Continue to Platform'
          )}
        </button>
      </div>
    </div>
  )
}
