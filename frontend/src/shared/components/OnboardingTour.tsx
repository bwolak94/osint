import { useState, useEffect } from "react";
import { X, ArrowRight, ArrowLeft } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { motion } from "framer-motion";

interface TourStep {
  target: string;  // CSS selector
  title: string;
  content: string;
  position: "top" | "bottom" | "left" | "right";
}

const tourSteps: TourStep[] = [
  { target: "[data-tour='sidebar']", title: "Navigation", content: "Use the sidebar to navigate between Dashboard, Investigations, Scanners, and Settings.", position: "right" },
  { target: "[data-tour='new-investigation']", title: "Create Investigation", content: "Click here to start a new OSINT investigation. Choose from templates or configure manually.", position: "bottom" },
  { target: "[data-tour='scanners']", title: "Available Scanners", content: "Browse all available scanners — from email lookups to domain analysis and breach detection.", position: "right" },
  { target: "[data-tour='settings']", title: "Settings", content: "Configure your profile, security settings, API keys, and notification preferences.", position: "right" },
];

export function OnboardingTour() {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const seen = localStorage.getItem("onboarding_complete");
    if (!seen) setActive(true);
  }, []);

  const complete = () => {
    setActive(false);
    localStorage.setItem("onboarding_complete", "true");
  };

  if (!active) return null;

  const current = tourSteps[step];
  if (!current) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/40" />
      <motion.div
        key={step}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm rounded-xl border p-5 shadow-2xl"
        style={{ background: "var(--bg-surface)", borderColor: "var(--border-default)" }}
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium" style={{ color: "var(--text-tertiary)" }}>
            Step {step + 1} of {tourSteps.length}
          </span>
          <button onClick={complete} className="rounded p-1 hover:bg-bg-overlay">
            <X className="h-4 w-4" style={{ color: "var(--text-tertiary)" }} />
          </button>
        </div>
        <h3 className="text-base font-semibold mb-1" style={{ color: "var(--text-primary)" }}>{current.title}</h3>
        <p className="text-sm mb-4" style={{ color: "var(--text-secondary)" }}>{current.content}</p>
        <div className="flex justify-between">
          <Button variant="ghost" size="sm" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Button>
          {step < tourSteps.length - 1 ? (
            <Button size="sm" onClick={() => setStep(step + 1)}>
              Next <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button size="sm" onClick={complete}>Get Started</Button>
          )}
        </div>
      </motion.div>
    </div>
  );
}
