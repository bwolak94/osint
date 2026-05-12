import { Suspense } from "react";
import { LoadingSpinner } from "@/shared/components/LoadingSpinner";
import { FeatureErrorBoundary } from "@/shared/components/FeatureErrorBoundary";

interface LazyProps {
  children: React.ReactNode;
  name: string;
}

export function Lazy({ children, name }: LazyProps) {
  return (
    <FeatureErrorBoundary featureName={name}>
      <Suspense fallback={<LoadingSpinner size="lg" className="mt-32" />}>
        {children}
      </Suspense>
    </FeatureErrorBoundary>
  );
}
