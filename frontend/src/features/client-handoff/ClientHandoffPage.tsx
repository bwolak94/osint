import { useState } from "react";
import { Package, Plus, ShieldCheck, Download, Check, X } from "lucide-react";
import { Badge } from "@/shared/components/Badge";
import { Button } from "@/shared/components/Button";
import { Card, CardHeader, CardBody } from "@/shared/components/Card";
import { Input } from "@/shared/components/Input";
import { useHandoffPackages, useCreatePackage, usePreparePackage } from "./hooks";
import type { HandoffPackage, HandoffItem } from "./types";

const STATUS_VARIANT: Record<string, "neutral" | "warning" | "success"> = {
  preparing: "warning",
  ready: "success",
  delivered: "neutral",
};

const ITEM_TYPES = ["report", "executive_slides", "remediation_guide", "evidence_archive", "scan_logs"];

function ItemRow({ item }: { item: HandoffItem }) {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded`} style={{ background: item.included ? "var(--success-900)" : "var(--bg-elevated)" }}>
        {item.included
          ? <Check className="h-3 w-3" style={{ color: "var(--success-400)" }} />
          : <X className="h-3 w-3" style={{ color: "var(--text-tertiary)" }} />
        }
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium" style={{ color: item.included ? "var(--text-primary)" : "var(--text-tertiary)" }}>{item.title}</p>
        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>{item.description}</p>
      </div>
      <span className="shrink-0 text-xs" style={{ color: "var(--text-tertiary)" }}>{item.size_mb} MB</span>
    </div>
  );
}

function PackageCard({ pkg }: { pkg: HandoffPackage }) {
  const prepare = usePreparePackage();
  const includedItems = pkg.items.filter((i) => i.included);
  const totalMb = includedItems.reduce((s, i) => s + i.size_mb, 0);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Package className="h-4 w-4" style={{ color: "var(--brand-500)" }} />
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>{pkg.name}</span>
              <Badge variant={(STATUS_VARIANT[pkg.status] ?? "neutral") as "success" | "warning" | "danger" | "info" | "neutral" | "brand"} size="sm" dot>{pkg.status}</Badge>
            </div>
            <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
              Client: {pkg.client_name} · {includedItems.length} items · {totalMb.toFixed(1)} MB
            </p>
          </div>
          {pkg.status === "preparing" && (
            <Button size="sm" leftIcon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={() => prepare.mutate(pkg.id)} loading={prepare.isPending}>
              Prepare & Sign
            </Button>
          )}
          {pkg.status === "ready" && pkg.download_token && (
            <Button size="sm" variant="ghost" leftIcon={<Download className="h-3.5 w-3.5" />}>
              Download
            </Button>
          )}
        </div>
      </CardHeader>
      <CardBody className="space-y-1">
        <div className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
          {pkg.items.map((item, i) => <ItemRow key={i} item={item} />)}
        </div>
        {pkg.checksum_sha256 && (
          <div className="pt-2">
            <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
              SHA256: <code className="font-mono" style={{ color: "var(--text-secondary)" }}>{pkg.checksum_sha256.slice(0, 32)}...</code>
              {pkg.pgp_signed && <span className="ml-2 inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium bg-success-900 text-success-500 border-success-500/20">PGP Signed</span>}
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export function ClientHandoffPage() {
  const { data: packages = [], isLoading } = useHandoffPackages();
  const createPackage = useCreatePackage();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [engId, setEngId] = useState("");
  const [clientName, setClientName] = useState("");
  const [selectedItems, setSelectedItems] = useState<string[]>(["report", "executive_slides", "remediation_guide"]);

  const toggleItem = (t: string) => {
    setSelectedItems((prev) => prev.includes(t) ? prev.filter((i) => i !== t) : [...prev, t]);
  };

  const handleCreate = () => {
    if (!name.trim() || !clientName.trim()) return;
    createPackage.mutate({ name: name.trim(), engagement_id: engId.trim() || "demo", client_name: clientName.trim(), include_items: selectedItems }, {
      onSuccess: () => { setShowForm(false); setName(""); setClientName(""); setEngId(""); },
    });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="h-6 w-6" style={{ color: "var(--brand-500)" }} />
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>Secure Client Handoff</h1>
          <Badge variant="neutral" size="sm">{packages.length} packages</Badge>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setShowForm((p) => !p)}>
          New Package
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody className="space-y-3">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Create Handoff Package</h3>
            <Input placeholder="Package name" value={name} onChange={(e) => setName(e.target.value)} />
            <Input placeholder="Client name" value={clientName} onChange={(e) => setClientName(e.target.value)} />
            <Input placeholder="Engagement ID (optional)" value={engId} onChange={(e) => setEngId(e.target.value)} />
            <div>
              <p className="mb-2 text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>Include items</p>
              <div className="space-y-1">
                {ITEM_TYPES.map((t) => (
                  <label key={t} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedItems.includes(t)}
                      onChange={() => toggleItem(t)}
                      className="rounded"
                    />
                    <span className="text-sm" style={{ color: "var(--text-secondary)" }}>{t.replace("_", " ")}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} loading={createPackage.isPending}>Create</Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm" style={{ color: "var(--text-tertiary)" }}>Loading...</div>
      ) : packages.length === 0 ? (
        <Card><CardBody><p className="text-center text-sm" style={{ color: "var(--text-tertiary)" }}>No handoff packages yet.</p></CardBody></Card>
      ) : (
        <div className="space-y-4">
          {packages.map((p) => <PackageCard key={p.id} pkg={p} />)}
        </div>
      )}
    </div>
  );
}
