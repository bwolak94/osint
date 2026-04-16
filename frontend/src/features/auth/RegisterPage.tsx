import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Shield, Mail, Lock, User, Building2, ArrowRight, ArrowLeft, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";

const step1Schema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Minimum 8 characters"),
  confirmPassword: z.string(),
}).refine((d) => d.password === d.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

const step2Schema = z.object({
  fullName: z.string().min(2, "Name is required"),
  companyName: z.string().optional(),
  termsAccepted: z.literal(true, { errorMap: () => ({ message: "Required" }) }),
  privacyAccepted: z.literal(true, { errorMap: () => ({ message: "Required" }) }),
  marketingConsent: z.boolean().default(false),
});

type Step1Data = z.infer<typeof step1Schema>;
type Step2Data = z.infer<typeof step2Schema>;

function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;

  if (score <= 1) return { score, label: "Weak", color: "var(--danger-500)" };
  if (score <= 2) return { score, label: "Fair", color: "var(--warning-500)" };
  if (score <= 3) return { score, label: "Good", color: "var(--info-500)" };
  return { score, label: "Strong", color: "var(--success-500)" };
}

export function RegisterPage() {
  const [step, setStep] = useState(1);
  const [step1Data, setStep1Data] = useState<Step1Data | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const form1 = useForm<Step1Data>({ resolver: zodResolver(step1Schema) });
  const form2 = useForm<Step2Data>({ resolver: zodResolver(step2Schema), defaultValues: { marketingConsent: false } });

  const watchPassword = form1.watch("password") || "";
  const strength = getPasswordStrength(watchPassword);
  const checks = [
    { label: "8+ characters", met: watchPassword.length >= 8 },
    { label: "Uppercase letter", met: /[A-Z]/.test(watchPassword) },
    { label: "Number", met: /[0-9]/.test(watchPassword) },
    { label: "Special character", met: /[^A-Za-z0-9]/.test(watchPassword) },
  ];

  const onStep1 = (data: Step1Data) => {
    setStep1Data(data);
    setStep(2);
  };

  const onStep2 = async (data: Step2Data) => {
    setLoading(true);
    try {
      // TODO: API call with { ...step1Data, ...data }
      navigate("/login");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ background: "var(--bg-base)" }}>
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <Shield className="mx-auto h-10 w-10" style={{ color: "var(--brand-500)" }} />
          <h1 className="mt-4 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Create your account
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Step {step} of 2
          </p>
          {/* Step indicator */}
          <div className="mx-auto mt-4 flex max-w-[120px] gap-2">
            <div className="h-1 flex-1 rounded-full" style={{ background: "var(--brand-500)" }} />
            <div className="h-1 flex-1 rounded-full" style={{ background: step === 2 ? "var(--brand-500)" : "var(--bg-elevated)" }} />
          </div>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 ? (
            <motion.form
              key="step1"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              onSubmit={form1.handleSubmit(onStep1)}
              className="space-y-4"
            >
              <Input label="Email" type="email" placeholder="you@example.com" prefixIcon={<Mail className="h-4 w-4" />} error={form1.formState.errors.email?.message} autoFocus {...form1.register("email")} />
              <div className="space-y-2">
                <Input label="Password" type="password" placeholder="Minimum 8 characters" prefixIcon={<Lock className="h-4 w-4" />} error={form1.formState.errors.password?.message} {...form1.register("password")} />
                {watchPassword && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1 flex-1 overflow-hidden rounded-full" style={{ background: "var(--bg-elevated)" }}>
                        <div className="h-full rounded-full transition-all" style={{ width: `${(strength.score / 5) * 100}%`, background: strength.color }} />
                      </div>
                      <span className="text-xs font-medium" style={{ color: strength.color }}>{strength.label}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-1">
                      {checks.map(({ label, met }) => (
                        <div key={label} className="flex items-center gap-1.5">
                          <Check className="h-3 w-3" style={{ color: met ? "var(--success-500)" : "var(--text-tertiary)" }} />
                          <span className="text-xs" style={{ color: met ? "var(--text-secondary)" : "var(--text-tertiary)" }}>{label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <Input label="Confirm Password" type="password" placeholder="Repeat your password" prefixIcon={<Lock className="h-4 w-4" />} error={form1.formState.errors.confirmPassword?.message} {...form1.register("confirmPassword")} />
              <Button type="submit" className="w-full" rightIcon={<ArrowRight className="h-4 w-4" />}>Continue</Button>
            </motion.form>
          ) : (
            <motion.form
              key="step2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              onSubmit={form2.handleSubmit(onStep2)}
              className="space-y-4"
            >
              <Input label="Full Name" placeholder="John Doe" prefixIcon={<User className="h-4 w-4" />} error={form2.formState.errors.fullName?.message} autoFocus {...form2.register("fullName")} />
              <Input label="Company (optional)" placeholder="Acme Inc." prefixIcon={<Building2 className="h-4 w-4" />} {...form2.register("companyName")} />
              <div className="space-y-3 rounded-md p-3" style={{ background: "var(--bg-elevated)" }}>
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="mt-0.5 accent-[var(--brand-500)]" {...form2.register("termsAccepted")} />
                  <span style={{ color: "var(--text-secondary)" }}>I agree to the <a href="#" className="underline" style={{ color: "var(--brand-500)" }}>Terms of Service</a></span>
                </label>
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="mt-0.5 accent-[var(--brand-500)]" {...form2.register("privacyAccepted")} />
                  <span style={{ color: "var(--text-secondary)" }}>I agree to the <a href="#" className="underline" style={{ color: "var(--brand-500)" }}>Privacy Policy</a></span>
                </label>
                <label className="flex items-start gap-2 text-sm cursor-pointer">
                  <input type="checkbox" className="mt-0.5 accent-[var(--brand-500)]" {...form2.register("marketingConsent")} />
                  <span style={{ color: "var(--text-tertiary)" }}>I agree to receive marketing communications</span>
                </label>
                {(form2.formState.errors.termsAccepted || form2.formState.errors.privacyAccepted) && (
                  <p className="text-xs" style={{ color: "var(--danger-500)" }}>You must accept the Terms and Privacy Policy</p>
                )}
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={() => setStep(1)} leftIcon={<ArrowLeft className="h-4 w-4" />}>Back</Button>
                <Button type="submit" loading={loading} className="flex-1">Create Account</Button>
              </div>
            </motion.form>
          )}
        </AnimatePresence>

        <p className="text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          Already have an account?{" "}
          <Link to="/login" className="font-medium" style={{ color: "var(--brand-500)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
