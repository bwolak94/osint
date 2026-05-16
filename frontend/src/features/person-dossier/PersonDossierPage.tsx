import { useState } from "react";
import { User, FileText, Mail, Phone, MapPin, Link, AlertTriangle, Download } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/shared/api/client";

interface PersonDossier {
  investigation_id: string;
  subject_name: string | null;
  emails: string[];
  phones: string[];
  usernames: string[];
  locations: string[];
  social_profiles: Array<{ platform: string; url: string; username: string }>;
  employment: Array<{ company: string; title: string; period: string }>;
  domains_linked: string[];
  crypto_addresses: string[];
  data_breach_exposure: Array<{ source: string; breach_name: string; records: number | null }>;
  risk_indicators: string[];
  confidence_score: number;
  total_sources: number;
  raw_finding_count: number;
}

export function PersonDossierPage() {
  const [investigationId, setInvestigationId] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [loading, setLoading] = useState(false);
  const [dossier, setDossier] = useState<PersonDossier | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!investigationId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.post<PersonDossier>("/api/v1/dossier/generate", {
        investigation_id: investigationId,
        subject_name: subjectName || null,
      });
      setDossier(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate dossier");
    } finally {
      setLoading(false);
    }
  };

  const confidence = dossier ? Math.round(dossier.confidence_score * 100) : 0;
  const confidenceColor = confidence >= 70 ? "text-green-400" : confidence >= 40 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <User className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Person Dossier Generator</h1>
          <p className="text-sm text-gray-400">Aggregate investigation findings into a structured subject profile</p>
        </div>
      </div>

      <Card className="bg-gray-900 border-gray-700">
        <CardContent className="pt-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Investigation ID</label>
              <Input
                placeholder="Enter investigation UUID"
                value={investigationId}
                onChange={(e) => setInvestigationId(e.target.value)}
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Subject Name (optional)</label>
              <Input
                placeholder="e.g. John Doe"
                value={subjectName}
                onChange={(e) => setSubjectName(e.target.value)}
                className="bg-gray-800 border-gray-700 text-white"
              />
            </div>
          </div>
          <Button onClick={handleGenerate} disabled={loading || !investigationId.trim()}
                  className="bg-blue-600 hover:bg-blue-700">
            {loading ? "Generating..." : "Generate Dossier"}
          </Button>
          {error && <p className="text-red-400 text-sm">{error}</p>}
        </CardContent>
      </Card>

      {dossier && (
        <div className="space-y-4">
          {/* Header stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: "Confidence", value: `${confidence}%`, color: confidenceColor },
              { label: "Sources", value: dossier.total_sources, color: "text-blue-400" },
              { label: "Findings", value: dossier.raw_finding_count, color: "text-purple-400" },
              { label: "Risk Indicators", value: dossier.risk_indicators.length, color: "text-red-400" },
            ].map((stat) => (
              <Card key={stat.label} className="bg-gray-900 border-gray-700">
                <CardContent className="pt-4">
                  <p className="text-xs text-gray-400">{stat.label}</p>
                  <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Emails */}
            {dossier.emails.length > 0 && (
              <Card className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Mail className="h-4 w-4 text-blue-400" />Email Addresses</CardTitle></CardHeader>
                <CardContent><div className="flex flex-wrap gap-2">{dossier.emails.map((e) => <Badge key={e} variant="secondary" className="text-xs font-mono">{e}</Badge>)}</div></CardContent>
              </Card>
            )}

            {/* Phones */}
            {dossier.phones.length > 0 && (
              <Card className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Phone className="h-4 w-4 text-green-400" />Phone Numbers</CardTitle></CardHeader>
                <CardContent><div className="flex flex-wrap gap-2">{dossier.phones.map((p) => <Badge key={p} variant="secondary" className="text-xs font-mono">{p}</Badge>)}</div></CardContent>
              </Card>
            )}

            {/* Usernames */}
            {dossier.usernames.length > 0 && (
              <Card className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><User className="h-4 w-4 text-purple-400" />Usernames</CardTitle></CardHeader>
                <CardContent><div className="flex flex-wrap gap-2">{dossier.usernames.map((u) => <Badge key={u} className="text-xs bg-purple-900/50 text-purple-200">@{u}</Badge>)}</div></CardContent>
              </Card>
            )}

            {/* Locations */}
            {dossier.locations.length > 0 && (
              <Card className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><MapPin className="h-4 w-4 text-yellow-400" />Locations</CardTitle></CardHeader>
                <CardContent><div className="flex flex-wrap gap-2">{dossier.locations.map((l) => <Badge key={l} className="text-xs bg-yellow-900/50 text-yellow-200">{l}</Badge>)}</div></CardContent>
              </Card>
            )}

            {/* Employment */}
            {dossier.employment.length > 0 && (
              <Card className="bg-gray-900 border-gray-700">
                <CardHeader className="pb-2"><CardTitle className="text-sm">Employment History</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {dossier.employment.map((e, i) => (
                    <div key={i} className="text-sm">
                      <span className="text-white font-medium">{e.company}</span>
                      {e.title && <span className="text-gray-400 ml-2">— {e.title}</span>}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Breach Exposure */}
            {dossier.data_breach_exposure.length > 0 && (
              <Card className="bg-gray-900 border-red-900">
                <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2 text-red-400"><AlertTriangle className="h-4 w-4" />Data Breach Exposure</CardTitle></CardHeader>
                <CardContent className="space-y-1">
                  {dossier.data_breach_exposure.map((b, i) => (
                    <div key={i} className="text-sm flex items-center justify-between">
                      <span className="text-white">{b.breach_name || b.source}</span>
                      {b.records && <Badge variant="destructive" className="text-xs">{b.records.toLocaleString()} records</Badge>}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Risk indicators */}
          {dossier.risk_indicators.length > 0 && (
            <Card className="bg-gray-900 border-red-900">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-red-400">Risk Indicators</CardTitle></CardHeader>
              <CardContent className="space-y-1">
                {dossier.risk_indicators.map((r, i) => (
                  <p key={i} className="text-sm text-gray-300">• {r}</p>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
