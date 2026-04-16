import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export function Card({ children, className = "", hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={`rounded-lg border transition-all ${
        hover
          ? "cursor-pointer hover:border-brand-500/30 hover:shadow-glow"
          : ""
      } ${onClick ? "cursor-pointer" : ""} ${className}`}
      style={{
        background: "var(--bg-surface)",
        borderColor: "var(--border-subtle)",
      }}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`border-b px-5 py-4 ${className}`}
      style={{ borderColor: "var(--border-subtle)" }}
    >
      {children}
    </div>
  );
}

export function CardBody({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>;
}

export function CardFooter({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`border-t px-5 py-3 ${className}`}
      style={{ borderColor: "var(--border-subtle)" }}
    >
      {children}
    </div>
  );
}
