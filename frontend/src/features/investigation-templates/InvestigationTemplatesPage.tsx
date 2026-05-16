import { useEffect, useState } from "react";
import { LayoutTemplate, Clock, Tag, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import apiClient from "@/shared/api/client";

interface InvestigationTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  input_types: string[];
  scanners: string[];
  estimated_time_seconds: number;
  tags: string[];
}

const CATEGORY_COLORS: Record<string, string> = {
  "Person OSINT": "bg-blue-900/50 text-blue-300",
  "Domain OSINT": "bg-green-900/50 text-green-300",
  "Corporate OSINT": "bg-purple-900/50 text-purple-300",
  "Threat Intelligence": "bg-red-900/50 text-red-300",
  "Security Assessment": "bg-orange-900/50 text-orange-300",
  "Financial OSINT": "bg-yellow-900/50 text-yellow-300",
  "Vehicle OSINT": "bg-gray-700 text-gray-300",
  "Social OSINT": "bg-pink-900/50 text-pink-300",
};

export function InvestigationTemplatesPage() {
  const [templates, setTemplates] = useState<InvestigationTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    apiClient.get<{ templates: InvestigationTemplate[] }>("/api/v1/investigation-templates")
      .then(({ data }) => setTemplates(data.templates))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const categories = Array.from(new Set(templates.map((t) => t.category)));
  const filtered = selectedCategory
    ? templates.filter((t) => t.category === selectedCategory)
    : templates;

  const formatTime = (secs: number) => {
    if (secs < 60) return `${secs}s`;
    return `~${Math.round(secs / 60)}m`;
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <LayoutTemplate className="h-7 w-7 text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">Investigation Templates</h1>
          <p className="text-sm text-gray-400">Pre-configured scan profiles for common OSINT use cases</p>
        </div>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1 rounded text-sm transition-colors ${!selectedCategory ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat === selectedCategory ? null : cat)}
            className={`px-3 py-1 rounded text-sm transition-colors ${selectedCategory === cat ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}
          >
            {cat}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-40 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((t) => (
            <Card key={t.id} className="bg-gray-900 border-gray-700 hover:border-gray-600 transition-colors cursor-pointer group">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-base text-white">{t.name}</CardTitle>
                  <Badge className={CATEGORY_COLORS[t.category] || "bg-gray-700 text-gray-300"}>
                    {t.category}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-gray-400">{t.description}</p>
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />{formatTime(t.estimated_time_seconds)}
                  </span>
                  <span>{t.scanners.length} scanners</span>
                  <span>Input: {t.input_types.join(", ")}</span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {t.tags.map((tag) => (
                    <Badge key={tag} className="text-xs bg-gray-800 text-gray-400">
                      <Tag className="h-2.5 w-2.5 mr-1" />{tag}
                    </Badge>
                  ))}
                </div>
                <Button size="sm" variant="ghost" className="w-full justify-between text-blue-400 hover:text-blue-300 hover:bg-gray-800">
                  Use Template <ChevronRight className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
