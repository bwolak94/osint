import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { Button } from "@/shared/components/Button";
import { Badge } from "@/shared/components/Badge";
import { Lock, Monitor, Smartphone, AlertTriangle, Trash2, Check } from "lucide-react";

const mockSessions = [
  { id: "1", device: "MacBook Pro", browser: "Chrome 131", location: "Warsaw, PL", lastActive: "2 min ago", current: true },
  { id: "2", device: "iPhone 15", browser: "Safari 18", location: "Warsaw, PL", lastActive: "3 hours ago", current: false },
  { id: "3", device: "Windows PC", browser: "Firefox 133", location: "Krakow, PL", lastActive: "2 days ago", current: false },
];

export function SecuritySettings() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [sessions, setSessions] = useState(mockSessions);
  const [showRevokeAll, setShowRevokeAll] = useState(false);

  const revokeSession = (id: string) => setSessions((s) => s.filter((x) => x.id !== id));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Security</h2>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Manage your password and sessions</p>
      </div>

      {/* Password */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Change Password</h3></CardHeader>
        <CardBody className="space-y-4">
          <Input label="Current Password" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} prefixIcon={<Lock className="h-4 w-4" />} />
          <Input label="New Password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} prefixIcon={<Lock className="h-4 w-4" />} helperText="Minimum 8 characters" />
          <Input label="Confirm New Password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} prefixIcon={<Lock className="h-4 w-4" />} error={confirmPassword && newPassword !== confirmPassword ? "Passwords don't match" : undefined} />
          <Button disabled={!currentPassword || !newPassword || newPassword !== confirmPassword}>Change Password</Button>
        </CardBody>
      </Card>

      {/* Sessions */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Active Sessions</h3>
          <Button variant="danger" size="sm" onClick={() => setShowRevokeAll(true)}>Revoke All Others</Button>
        </CardHeader>
        <CardBody className="p-0">
          {sessions.map((s) => (
            <div key={s.id} className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
              <div className="flex items-center gap-3">
                {s.device.includes("iPhone") ? <Smartphone className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} /> : <Monitor className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{s.device} — {s.browser}</span>
                    {s.current && <Badge variant="success" size="sm">Current</Badge>}
                  </div>
                  <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>{s.location} · {s.lastActive}</span>
                </div>
              </div>
              {!s.current && (
                <Button variant="ghost" size="sm" onClick={() => revokeSession(s.id)}>Revoke</Button>
              )}
            </div>
          ))}
        </CardBody>
      </Card>

      {/* 2FA placeholder */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Two-Factor Authentication</h3></CardHeader>
        <CardBody>
          <div className="flex items-center gap-3 rounded-md p-3" style={{ background: "var(--bg-elevated)" }}>
            <Badge variant="neutral" size="sm">Coming Soon</Badge>
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>2FA support will be available in a future update.</span>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
