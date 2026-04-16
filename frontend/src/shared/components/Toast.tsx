import { useState, useEffect } from "react";
import { X, CheckCircle2, AlertTriangle, AlertCircle, Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

const icons = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const colors = {
  success: { bg: "var(--success-900)", text: "var(--success-500)", border: "var(--success-500)" },
  error: { bg: "var(--danger-900)", text: "var(--danger-500)", border: "var(--danger-500)" },
  warning: { bg: "var(--warning-900)", text: "var(--warning-500)", border: "var(--warning-500)" },
  info: { bg: "var(--info-900)", text: "var(--info-500)", border: "var(--info-500)" },
};

// Global toast state
let _toasts: Toast[] = [];
let _listeners: Array<(toasts: Toast[]) => void> = [];

function notify(listeners: typeof _listeners) {
  listeners.forEach((l) => l([..._toasts]));
}

export const toast = {
  success: (message: string) => {
    const t = { id: Date.now().toString(), type: "success" as const, message };
    _toasts = [..._toasts.slice(-4), t];
    notify(_listeners);
    setTimeout(() => { _toasts = _toasts.filter((x) => x.id !== t.id); notify(_listeners); }, 4000);
  },
  error: (message: string) => {
    const t = { id: Date.now().toString(), type: "error" as const, message };
    _toasts = [..._toasts.slice(-4), t];
    notify(_listeners);
    setTimeout(() => { _toasts = _toasts.filter((x) => x.id !== t.id); notify(_listeners); }, 6000);
  },
  warning: (message: string) => {
    const t = { id: Date.now().toString(), type: "warning" as const, message };
    _toasts = [..._toasts.slice(-4), t];
    notify(_listeners);
    setTimeout(() => { _toasts = _toasts.filter((x) => x.id !== t.id); notify(_listeners); }, 5000);
  },
  info: (message: string) => {
    const t = { id: Date.now().toString(), type: "info" as const, message };
    _toasts = [..._toasts.slice(-4), t];
    notify(_listeners);
    setTimeout(() => { _toasts = _toasts.filter((x) => x.id !== t.id); notify(_listeners); }, 4000);
  },
};

export function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    _listeners.push(setToasts);
    return () => { _listeners = _listeners.filter((l) => l !== setToasts); };
  }, []);

  const dismiss = (id: string) => {
    _toasts = _toasts.filter((t) => t.id !== id);
    notify(_listeners);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" style={{ maxWidth: 380 }}>
      <AnimatePresence>
        {toasts.map((t) => {
          const Icon = icons[t.type];
          const color = colors[t.type];
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, x: 50, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 50, scale: 0.95 }}
              className="flex items-start gap-2 rounded-lg border px-4 py-3 shadow-lg"
              style={{ background: color.bg, borderColor: `${color.border}30` }}
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: color.text }} />
              <p className="flex-1 text-sm" style={{ color: color.text }}>{t.message}</p>
              <button onClick={() => dismiss(t.id)} className="shrink-0">
                <X className="h-3.5 w-3.5" style={{ color: color.text }} />
              </button>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
