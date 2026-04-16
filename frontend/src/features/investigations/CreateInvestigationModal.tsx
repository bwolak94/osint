import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Plus, Trash2, Tag, ArrowRight, ArrowLeft, Zap, CheckSquare, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { Badge } from "@/shared/components/Badge";
import { useCreateInvestigation } from "./hooks";

interface Props {
  onClose: () => void;
}

const seedTypes = [
  { value: "email", label: "Email" },
  { value: "username", label: "Username" },
  { value: "nip", label: "NIP" },
  { value: "phone", label: "Phone" },
  { value: "url", label: "URL" },
  { value: "company_name", label: "Company" },
  { value: "domain", label: "Domain" },
] as const;

// Scanner definitions with supported input types
const AVAILABLE_SCANNERS = [
  {
    name: "holehe",
    label: "Holehe",
    description: "Check email registration across 120+ services (Instagram, Twitter, Spotify, etc.)",
    inputTypes: ["email"],
  },
  {
    name: "maigret",
    label: "Maigret",
    description: "Find username presence across 3000+ websites",
    inputTypes: ["username"],
  },
  {
    name: "vat_status",
    label: "VAT Status",
    description: "Check VAT registration status and bank accounts (Polish Biala Lista API)",
    inputTypes: ["nip"],
  },
  {
    name: "playwright_krs",
    label: "KRS Scraper",
    description: "Scrape KRS company registry for board members and registration data",
    inputTypes: ["nip"],
  },
  {
    name: "playwright_ceidg",
    label: "CEIDG Scraper",
    description: "Search CEIDG for sole proprietorship data",
    inputTypes: ["nip"],
  },
  {
    name: "whois",
    label: "WHOIS Lookup",
    description: "Domain ownership, registrar, nameservers, and registration dates",
    inputTypes: ["domain"],
  },
  {
    name: "dns_lookup",
    label: "DNS Records",
    description: "A, MX, NS, TXT records and IP resolution",
    inputTypes: ["domain"],
  },
] as const;

const schema = z.object({
  title: z.string().min(3, "Min 3 characters").max(200),
  description: z.string().max(2000).optional(),
  tags: z.array(z.string()).max(20).default([]),
  seeds: z.array(z.object({
    type: z.string().min(1),
    value: z.string().min(1, "Required"),
  })).min(1, "Add at least one seed input").max(10),
  startImmediately: z.boolean().default(false),
  enabledScanners: z.array(z.string()).default([]),
});

type FormData = z.infer<typeof schema>;

// Simple NIP checksum validation
function isValidNIP(nip: string): boolean {
  const cleaned = nip.replace(/[\s-]/g, "");
  if (cleaned.length !== 10 || !/^\d+$/.test(cleaned)) return false;
  const weights = [6, 5, 7, 2, 3, 4, 5, 6, 7];
  const digits = cleaned.split("").map(Number);
  const sum = weights.reduce((acc, w, i) => acc + w * digits[i], 0);
  return sum % 11 === digits[9];
}

const templates = [
  { name: "Email OSINT", desc: "Full email investigation", seeds: [{ type: "email", value: "" }], scanners: ["holehe"] },
  { name: "Company Deep Dive", desc: "NIP + VAT + KRS + CEIDG", seeds: [{ type: "nip", value: "" }], scanners: ["vat_status", "playwright_krs", "playwright_ceidg"] },
  { name: "Username Search", desc: "Find profiles across 3000+ sites", seeds: [{ type: "username", value: "" }], scanners: ["maigret"] },
  { name: "Custom", desc: "Configure manually", seeds: [], scanners: [] },
];

export function CreateInvestigationModal({ onClose }: Props) {
  const [step, setStep] = useState(1);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [formError, setFormError] = useState("");
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const navigate = useNavigate();
  const createMutation = useCreateInvestigation();

  const { register, control, handleSubmit, watch, setValue, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { seeds: [{ type: "email", value: "" }], tags: [], startImmediately: false, enabledScanners: [] },
  });

  const { fields, append, remove, replace } = useFieldArray({ control, name: "seeds" });
  const tags = watch("tags") ?? [];
  const seeds = watch("seeds");
  const enabledScanners = watch("enabledScanners") ?? [];

  const handleBulkImport = () => {
    const lines = bulkText.split("\n").map(l => l.trim()).filter(Boolean);
    const newSeeds = lines.map(line => {
      // Auto-detect type
      let type = "email";
      if (line.includes("@")) type = "email";
      else if (/^\d{10}$/.test(line.replace(/[-\s]/g, ""))) type = "nip";
      else if (line.startsWith("http")) type = "url";
      else if (line.includes(".")) type = "domain";
      else type = "username";
      return { type, value: line };
    });
    // Append to existing seeds
    for (const s of newSeeds) {
      if (fields.length < 10) append(s);
    }
    setShowBulkImport(false);
    setBulkText("");
  };

  const selectTemplate = (tpl: typeof templates[number]) => {
    setSelectedTemplate(tpl.name);
    if (tpl.seeds.length > 0) {
      replace(tpl.seeds);
    }
    if (tpl.scanners.length > 0) {
      setValue("enabledScanners", tpl.scanners);
    }
  };

  // Determine which scanners are applicable based on seed input types
  const applicableScanners = useMemo(() => {
    const seedInputTypes = new Set(seeds.map((s) => s.type));
    return AVAILABLE_SCANNERS.filter((scanner) =>
      scanner.inputTypes.some((t) => seedInputTypes.has(t))
    );
  }, [seeds]);

  // When moving to step 3, auto-select all applicable scanners if none are selected
  const goToStep3 = () => {
    if (enabledScanners.length === 0) {
      setValue("enabledScanners", applicableScanners.map((s) => s.name));
    }
    setStep(3);
  };

  const toggleScanner = (name: string) => {
    const current = enabledScanners;
    if (current.includes(name)) {
      setValue("enabledScanners", current.filter((s) => s !== name));
    } else {
      setValue("enabledScanners", [...current, name]);
    }
  };

  const addTag = () => {
    const t = tagInput.trim();
    if (t && !tags.includes(t) && tags.length < 20) {
      setValue("tags", [...tags, t]);
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    setValue("tags", tags.filter((existing) => existing !== tag));
  };

  const onSubmit = async (data: FormData) => {
    setFormError("");
    try {
      const result = await createMutation.mutateAsync({
        title: data.title,
        description: data.description,
        seed_inputs: data.seeds.map((s) => ({ type: s.type, value: s.value })),
        tags: data.tags,
        enabled_scanners: data.enabledScanners.length > 0 ? data.enabledScanners : undefined,
      });
      onClose();
      navigate(`/investigations/${result.id}`);
    } catch (err: any) {
      setFormError(err?.message ?? "Failed to create investigation");
    }
  };

  const totalSteps = 3;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.15 }}
        className="w-full max-w-lg rounded-xl border shadow-lg"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--border-subtle)" }}>
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            New Investigation — Step {step}/{totalSteps}
          </h2>
          <button onClick={onClose} className="rounded-md p-1 transition-colors hover:bg-bg-overlay">
            <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="max-h-[60vh] overflow-y-auto px-6 py-4">
            <AnimatePresence mode="wait">
              {step === 1 && (
                <motion.div key="s1" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }} className="space-y-4">
                  {/* Template selector */}
                  <div>
                    <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Start from a template</label>
                    <div className="grid grid-cols-2 gap-2">
                      {templates.map((tpl) => (
                        <button
                          key={tpl.name}
                          type="button"
                          onClick={() => selectTemplate(tpl)}
                          className={`rounded-lg border p-3 text-left transition-all ${
                            selectedTemplate === tpl.name
                              ? "border-brand-500 bg-brand-900/30"
                              : "border-border hover:bg-bg-overlay"
                          }`}
                          style={{ borderColor: selectedTemplate === tpl.name ? "var(--brand-500)" : "var(--border-default)" }}
                        >
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4" style={{ color: selectedTemplate === tpl.name ? "var(--brand-400)" : "var(--text-tertiary)" }} />
                            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{tpl.name}</span>
                          </div>
                          <p className="mt-1 text-xs" style={{ color: "var(--text-tertiary)" }}>{tpl.desc}</p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <Input label="Title" placeholder="Investigation #1 — XYZ Company" error={errors.title?.message} {...register("title")} autoFocus />
                  <div>
                    <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Description (optional)</label>
                    <textarea
                      className="block w-full rounded-md border px-3 py-2 text-sm"
                      style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                      rows={3}
                      placeholder="Brief description of the investigation purpose..."
                      {...register("description")}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium" style={{ color: "var(--text-secondary)" }}>Tags</label>
                    <div className="flex gap-2">
                      <input
                        className="flex-1 rounded-md border px-3 py-2 text-sm"
                        style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                        placeholder="Add tag + Enter"
                        value={tagInput}
                        onChange={(e) => setTagInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
                      />
                      <Button type="button" variant="secondary" size="sm" onClick={addTag}>
                        <Tag className="h-3 w-3" />
                      </Button>
                    </div>
                    {tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {tags.map((tag) => (
                          <Badge key={tag} variant="neutral" size="sm">
                            {tag}
                            <button type="button" onClick={() => removeTag(tag)} className="ml-1">
                              <X className="h-3 w-3" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}

              {step === 2 && (
                <motion.div key="s2" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="space-y-3">
                  <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    Seed Inputs ({fields.length}/10)
                  </p>
                  {fields.map((field, index) => {
                    const seedValue = watch(`seeds.${index}.value`);
                    const seedType = watch(`seeds.${index}.type`);
                    const nipValid = seedType === "nip" && seedValue ? isValidNIP(seedValue) : null;

                    return (
                      <div key={field.id} className="flex items-start gap-2">
                        <select
                          className="rounded-md border px-2 py-2 text-sm"
                          style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                          {...register(`seeds.${index}.type`)}
                        >
                          {seedTypes.map((t) => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                          ))}
                        </select>
                        <div className="relative flex-1">
                          <input
                            className={`w-full rounded-md border px-3 py-2 text-sm font-mono ${
                              nipValid === false ? "border-danger-500" : nipValid === true ? "border-success-500" : ""
                            }`}
                            style={{ background: "var(--bg-elevated)", borderColor: nipValid === null ? "var(--border-default)" : undefined, color: "var(--text-primary)" }}
                            placeholder={seedType === "email" ? "user@example.com" : seedType === "nip" ? "5261040828" : "Enter value..."}
                            {...register(`seeds.${index}.value`)}
                          />
                          {nipValid !== null && (
                            <span className={`absolute right-2 top-2 text-xs font-medium ${nipValid ? "text-success-500" : "text-danger-500"}`}>
                              {nipValid ? "Valid" : "Invalid"}
                            </span>
                          )}
                        </div>
                        {fields.length > 1 && (
                          <button type="button" onClick={() => remove(index)} className="rounded-md p-2 transition-colors hover:bg-bg-overlay">
                            <Trash2 className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
                          </button>
                        )}
                      </div>
                    );
                  })}
                  {errors.seeds?.message && (
                    <p className="text-xs" style={{ color: "var(--danger-500)" }}>{errors.seeds.message}</p>
                  )}
                  {fields.length < 10 && (
                    <div className="flex gap-2">
                      <Button type="button" variant="ghost" size="sm" onClick={() => append({ type: "email", value: "" })} leftIcon={<Plus className="h-3 w-3" />}>
                        Add seed input
                      </Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => setShowBulkImport(true)}>
                        Bulk Import
                      </Button>
                    </div>
                  )}
                  {showBulkImport && (
                    <div className="space-y-2 rounded-md border p-3" style={{ background: "var(--bg-elevated)", borderColor: "var(--border-default)" }}>
                      <textarea
                        rows={5}
                        className="w-full rounded-md border px-3 py-2 text-sm font-mono"
                        style={{ background: "var(--bg-base)", borderColor: "var(--border-default)", color: "var(--text-primary)" }}
                        placeholder="Paste one value per line (emails, NIPs, usernames, domains)..."
                        value={bulkText}
                        onChange={(e) => setBulkText(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button type="button" size="sm" onClick={handleBulkImport}>Import</Button>
                        <Button type="button" variant="ghost" size="sm" onClick={() => setShowBulkImport(false)}>Cancel</Button>
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {step === 3 && (
                <motion.div key="s3" initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="space-y-3">
                  <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    Select Scanners
                  </p>
                  <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
                    Only scanners compatible with your seed input types are shown. Deselect any you want to skip.
                  </p>

                  {applicableScanners.length === 0 ? (
                    <div className="rounded-md p-4 text-center text-sm" style={{ background: "var(--bg-elevated)", color: "var(--text-tertiary)" }}>
                      No scanners available for the selected seed input types.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {applicableScanners.map((scanner) => {
                        const isChecked = enabledScanners.includes(scanner.name);
                        return (
                          <label
                            key={scanner.name}
                            className="flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors hover:bg-bg-overlay"
                            style={{
                              borderColor: isChecked ? "var(--brand-500)" : "var(--border-default)",
                              background: isChecked ? "var(--bg-elevated)" : "transparent",
                            }}
                          >
                            <input
                              type="checkbox"
                              className="mt-0.5 accent-[var(--brand-500)]"
                              checked={isChecked}
                              onChange={() => toggleScanner(scanner.name)}
                            />
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                                  {scanner.label}
                                </span>
                                <Badge variant="neutral" size="sm">{scanner.name}</Badge>
                              </div>
                              <p className="mt-0.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
                                {scanner.description}
                              </p>
                              <div className="mt-1 flex gap-1">
                                {scanner.inputTypes.map((t) => (
                                  <Badge key={t} variant="info" size="sm">{t}</Badge>
                                ))}
                              </div>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  )}

                  <label className="mt-4 flex cursor-pointer items-center gap-2 rounded-md p-3" style={{ background: "var(--bg-elevated)" }}>
                    <input type="checkbox" className="accent-[var(--brand-500)]" {...register("startImmediately")} />
                    <div>
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Start scanning immediately</span>
                      <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>Begin scanning as soon as the investigation is created</p>
                    </div>
                    <Zap className="ml-auto h-4 w-4" style={{ color: "var(--brand-400)" }} />
                  </label>
                </motion.div>
              )}
            </AnimatePresence>

            {formError && (
              <div
                className="mt-3 rounded-md px-3 py-2 text-sm"
                style={{ background: "var(--danger-900)", color: "var(--danger-500)" }}
              >
                {formError}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between border-t px-6 py-4" style={{ borderColor: "var(--border-subtle)" }}>
            {step === 1 && (
              <>
                <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
                <Button type="button" onClick={() => setStep(2)} rightIcon={<ArrowRight className="h-4 w-4" />}>
                  Next: Seed Inputs
                </Button>
              </>
            )}
            {step === 2 && (
              <>
                <Button type="button" variant="ghost" onClick={() => setStep(1)} leftIcon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
                <Button type="button" onClick={goToStep3} rightIcon={<ArrowRight className="h-4 w-4" />}>
                  Next: Scanners
                </Button>
              </>
            )}
            {step === 3 && (
              <>
                <Button type="button" variant="ghost" onClick={() => setStep(2)} leftIcon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
                <Button type="submit" loading={createMutation.isPending}>Create Investigation</Button>
              </>
            )}
          </div>
        </form>
      </motion.div>
    </div>
  );
}
