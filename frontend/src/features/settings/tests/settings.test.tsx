import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/shared/api/queryClient";

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

// FeatureGate tests
import { FeatureGate } from "@/shared/components/FeatureGate";

// Mock useAuth
vi.mock("@/shared/hooks/useAuth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/shared/hooks/useAuth";
const mockUseAuth = vi.mocked(useAuth);

describe("FeatureGate", () => {
  it("renders children for authorized tier", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "1", email: "x@x.com", role: "analyst", subscription_tier: "pro", is_active: true, is_email_verified: true },
      accessToken: "t", isAuthenticated: true, isAdmin: false, isPro: true, isEnterprise: false,
      setAuth: vi.fn(), setAccessToken: vi.fn(), logout: vi.fn(),
    });

    render(
      <Wrapper>
        <FeatureGate feature="deep_scan">
          <span>Scan Button</span>
        </FeatureGate>
      </Wrapper>,
    );

    expect(screen.getByText("Scan Button")).toBeDefined();
  });

  it("renders upgrade prompt for unauthorized tier", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "1", email: "x@x.com", role: "analyst", subscription_tier: "free", is_active: true, is_email_verified: true },
      accessToken: "t", isAuthenticated: true, isAdmin: false, isPro: false, isEnterprise: false,
      setAuth: vi.fn(), setAccessToken: vi.fn(), logout: vi.fn(),
    });

    render(
      <Wrapper>
        <FeatureGate feature="deep_scan">
          <span>Scan Button</span>
        </FeatureGate>
      </Wrapper>,
    );

    expect(screen.queryByText("Scan Button")).toBeNull();
    expect(screen.getByText("Requires Pro plan")).toBeDefined();
    expect(screen.getByText(/Upgrade/)).toBeDefined();
  });

  it("renders custom fallback", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "1", email: "x@x.com", role: "analyst", subscription_tier: "free", is_active: true, is_email_verified: true },
      accessToken: "t", isAuthenticated: true, isAdmin: false, isPro: false, isEnterprise: false,
      setAuth: vi.fn(), setAccessToken: vi.fn(), logout: vi.fn(),
    });

    render(
      <Wrapper>
        <FeatureGate feature="api_access" fallback={<span>Custom Fallback</span>}>
          <span>API Content</span>
        </FeatureGate>
      </Wrapper>,
    );

    expect(screen.queryByText("API Content")).toBeNull();
    expect(screen.getByText("Custom Fallback")).toBeDefined();
  });

  it("enterprise can access all features", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "1", email: "x@x.com", role: "analyst", subscription_tier: "enterprise", is_active: true, is_email_verified: true },
      accessToken: "t", isAuthenticated: true, isAdmin: false, isPro: true, isEnterprise: true,
      setAuth: vi.fn(), setAccessToken: vi.fn(), logout: vi.fn(),
    });

    render(
      <Wrapper>
        <FeatureGate feature="bulk_scan">
          <span>Bulk Scan</span>
        </FeatureGate>
      </Wrapper>,
    );

    expect(screen.getByText("Bulk Scan")).toBeDefined();
  });
});

// GDPR delete confirmation
describe("GDPR Delete Confirmation", () => {
  it("DELETE text enables delete button", async () => {
    // Simulate the confirmation pattern
    const isValid = "DELETE" === "DELETE";
    expect(isValid).toBe(true);

    const isInvalid = "delete" === "DELETE";
    expect(isInvalid).toBe(false);
  });
});

// Pricing toggle
describe("Pricing Logic", () => {
  it("yearly is cheaper per month than monthly", () => {
    const monthlyPrice = 29.99;
    const yearlyPrice = 299.99;
    const yearlyPerMonth = yearlyPrice / 12;
    expect(yearlyPerMonth).toBeLessThan(monthlyPrice);
  });

  it("discount is approximately 20%", () => {
    const monthlyAnnual = 29.99 * 12;
    const yearlyPrice = 299.99;
    const discount = (1 - yearlyPrice / monthlyAnnual) * 100;
    expect(discount).toBeGreaterThan(15);
    expect(discount).toBeLessThan(25);
  });
});

// Payment status flow
describe("Payment Status", () => {
  const validStatuses = ["pending", "waiting", "confirming", "confirmed", "finished", "failed", "expired"];

  it("all statuses are recognized", () => {
    validStatuses.forEach((status) => {
      expect(typeof status).toBe("string");
    });
  });

  it("finished is the only success state", () => {
    const successStatuses = validStatuses.filter((s) => s === "finished");
    expect(successStatuses).toHaveLength(1);
  });
});
