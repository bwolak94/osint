import { useState } from "react";
import { Card, CardBody, CardHeader } from "@/shared/components/Card";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Badge } from "@/shared/components/Badge";
import { Download, AlertTriangle, Trash2, CheckCircle2 } from "lucide-react";

export function GdprSettings() {
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [exportRequested, setExportRequested] = useState(false);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Privacy & GDPR</h2>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>Your data, your rights</p>
      </div>

      {/* Data export */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Export Your Data</h3></CardHeader>
        <CardBody>
          <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>
            Download a copy of all your personal data in JSON format (GDPR Art. 20).
          </p>
          {exportRequested ? (
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" style={{ color: "var(--success-500)" }} />
              <span className="text-sm" style={{ color: "var(--success-500)" }}>Export queued. We'll email you when it's ready.</span>
            </div>
          ) : (
            <Button variant="secondary" leftIcon={<Download className="h-4 w-4" />} onClick={() => setExportRequested(true)}>
              Download My Data
            </Button>
          )}
        </CardBody>
      </Card>

      {/* Consent history */}
      <Card>
        <CardHeader><h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Consent History</h3></CardHeader>
        <CardBody className="space-y-2 p-0">
          {[
            { label: "Terms of Service", date: "Jan 15, 2025", required: true },
            { label: "Privacy Policy", date: "Jan 15, 2025", required: true },
            { label: "Marketing communications", date: "Jan 15, 2025", required: false, granted: true },
          ].map((c) => (
            <div key={c.label} className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: "var(--border-subtle)" }}>
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.label}</p>
                <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Granted: {c.date}</p>
              </div>
              {c.required ? (
                <Badge variant="neutral" size="sm">Required</Badge>
              ) : (
                <Button variant="ghost" size="sm">Withdraw</Button>
              )}
            </div>
          ))}
        </CardBody>
      </Card>

      {/* Delete account */}
      <Card className="border-danger-500/30">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" style={{ color: "var(--danger-500)" }} />
            <h3 className="text-sm font-semibold" style={{ color: "var(--danger-500)" }}>Danger Zone</h3>
          </div>
        </CardHeader>
        <CardBody>
          <p className="mb-3 text-sm" style={{ color: "var(--text-secondary)" }}>
            This will permanently delete your account and all associated data. This action cannot be undone.
          </p>

          {showDeleteDialog ? (
            <div className="space-y-3 rounded-md border p-4" style={{ background: "var(--bg-elevated)", borderColor: "var(--danger-500)" }}>
              <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                Type <span className="font-mono font-bold" style={{ color: "var(--danger-500)" }}>DELETE</span> to confirm
              </p>
              <Input
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                placeholder="Type DELETE"
                mono
              />
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  disabled={deleteConfirmation !== "DELETE"}
                >
                  Delete My Account
                </Button>
                <Button variant="ghost" onClick={() => { setShowDeleteDialog(false); setDeleteConfirmation(""); }}>
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="danger" leftIcon={<Trash2 className="h-4 w-4" />} onClick={() => setShowDeleteDialog(true)}>
              Request Account Deletion
            </Button>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
