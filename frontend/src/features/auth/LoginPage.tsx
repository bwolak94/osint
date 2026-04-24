import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Shield, Mail, Lock, Eye, EyeOff, Network, Search, Globe } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";
import { useAuthStore } from "@/features/auth/store";
import { apiClient, ApiError } from "@/shared/api/client";

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState("");
  const [shake, setShake] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    setFormError("");
    try {
      const res = await apiClient.post("/auth/login", data);
      setAuth(res.data.user, res.data.access_token);
      navigate("/investigations");
    } catch (err) {
      setShake(true);
      setTimeout(() => setShake(false), 500);

      if (err instanceof ApiError) {
        if (err.status === 423) {
          setFormError("Account temporarily locked. Try again in 15 minutes.");
        } else if (err.status === 429) {
          setFormError("Too many attempts. Please wait before trying again.");
        } else {
          setFormError("Invalid email or password");
        }
      } else {
        setFormError("An unexpected error occurred");
      }
    }
  };

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-base)" }}>
      {/* Left: Branding (hidden on mobile) */}
      <div
        className="hidden w-1/2 flex-col justify-between p-12 lg:flex"
        style={{ background: "var(--bg-surface)" }}
      >
        <div>
          <div className="flex items-center gap-3">
            <Shield className="h-8 w-8" style={{ color: "var(--brand-500)" }} />
            <span className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              OSINT Platform
            </span>
          </div>
        </div>

        <div className="space-y-6">
          <h2 className="text-4xl font-bold leading-tight tracking-tight" style={{ color: "var(--text-primary)" }}>
            Precision Intelligence
            <br />
            <span style={{ color: "var(--brand-500)" }}>Platform</span>
          </h2>
          <div className="space-y-4">
            {[
              { icon: Search, text: "Scan 120+ services for digital footprints" },
              { icon: Network, text: "Build knowledge graphs automatically" },
              { icon: Globe, text: "Polish registry integration (KRS, CEIDG, VAT)" },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div
                  className="flex h-8 w-8 items-center justify-center rounded-lg"
                  style={{ background: "var(--brand-900)" }}
                >
                  <Icon className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
                </div>
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {text}
                </span>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
          &copy; {new Date().getFullYear()} OSINT Platform. All rights reserved.
        </p>
      </div>

      {/* Right: Login form */}
      <div className="flex flex-1 items-center justify-center px-6">
        <motion.div
          className="w-full max-w-sm space-y-8"
          animate={shake ? { x: [0, -10, 10, -10, 10, 0] } : {}}
          transition={{ duration: 0.4 }}
        >
          {/* Mobile logo */}
          <div className="text-center lg:hidden">
            <Shield className="mx-auto h-10 w-10" style={{ color: "var(--brand-500)" }} />
          </div>

          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
              Welcome back
            </h1>
            <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              Sign in to your account
            </p>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Email"
              type="email"
              placeholder="you@example.com"
              prefixIcon={<Mail className="h-4 w-4" />}
              {...(errors.email?.message ? { error: errors.email.message } : {})}
              autoFocus
              {...register("email")}
            />

            <div className="space-y-1.5">
              <Input
                label="Password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                prefixIcon={<Lock className="h-4 w-4" />}
                suffixIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="cursor-pointer"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
                {...(errors.password?.message ? { error: errors.password.message } : {})}
                {...register("password")}
              />
              <div className="text-right">
                <Link
                  to="/forgot-password"
                  className="text-xs font-medium"
                  style={{ color: "var(--brand-500)" }}
                >
                  Forgot password?
                </Link>
              </div>
            </div>

            {formError && (
              <div
                className="rounded-md px-3 py-2 text-sm"
                style={{ background: "var(--danger-900)", color: "var(--danger-500)" }}
              >
                {formError}
              </div>
            )}

            <Button type="submit" loading={isSubmitting} className="w-full">
              Sign In
            </Button>
          </form>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1" style={{ background: "var(--border-default)" }} />
            <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>or</span>
            <div className="h-px flex-1" style={{ background: "var(--border-default)" }} />
          </div>

          <p className="text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            Don't have an account?{" "}
            <Link to="/register" className="font-medium" style={{ color: "var(--brand-500)" }}>
              Create one
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  );
}
