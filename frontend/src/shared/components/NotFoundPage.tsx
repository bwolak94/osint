import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
      <p className="text-6xl font-bold" style={{ color: "var(--text-tertiary)" }}>404</p>
      <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
        Page not found
      </h1>
      <p className="text-sm max-w-sm" style={{ color: "var(--text-secondary)" }}>
        The page you are looking for doesn&apos;t exist or has been moved.
      </p>
      <Link
        to="/"
        className="mt-2 rounded-md px-4 py-2 text-sm font-medium transition-colors"
        style={{ background: "var(--brand-500)", color: "white" }}
      >
        Back to dashboard
      </Link>
    </div>
  );
}
