import { useState } from "react";
import { Link } from "react-router-dom";
import { Shield, Mail, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Button } from "@/shared/components/Button";
import { Input } from "@/shared/components/Input";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      // TODO: API call — always show success to prevent email enumeration
      await new Promise((r) => setTimeout(r, 1000));
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ background: "var(--bg-base)" }}>
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <Shield className="mx-auto h-10 w-10" style={{ color: "var(--brand-500)" }} />
          <h1 className="mt-4 text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            {submitted ? "Check your email" : "Reset password"}
          </h1>
        </div>

        {submitted ? (
          <div className="space-y-4 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12" style={{ color: "var(--success-500)" }} />
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              If an account with that email exists, we sent a password reset link.
            </p>
            <Link to="/login">
              <Button variant="secondary" leftIcon={<ArrowLeft className="h-4 w-4" />} className="mx-auto">
                Back to login
              </Button>
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input label="Email" type="email" placeholder="you@example.com" prefixIcon={<Mail className="h-4 w-4" />} value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
            <Button type="submit" loading={loading} className="w-full">Send Reset Link</Button>
            <div className="text-center">
              <Link to="/login" className="text-sm font-medium" style={{ color: "var(--brand-500)" }}>
                <ArrowLeft className="mr-1 inline h-3 w-3" />Back to login
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
