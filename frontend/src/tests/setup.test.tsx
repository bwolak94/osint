import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/shared/api/queryClient";

// Wrapper for components that need router + query context
function TestWrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

// ============== Button ==============
import { Button } from "@/shared/components/Button";

describe("Button", () => {
  it("renders with text content", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeDefined();
  });

  it("renders primary variant by default", () => {
    render(<Button>Primary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-brand-500");
  });

  it("renders secondary variant", () => {
    render(<Button variant="secondary">Secondary</Button>);
    const btn = screen.getByRole("button");
    expect(btn.className).toContain("bg-bg-elevated");
  });

  it("shows spinner when loading", () => {
    render(<Button loading>Submit</Button>);
    const btn = screen.getByRole("button");
    expect(btn.querySelector(".animate-spin")).not.toBeNull();
  });

  it("is disabled when loading", () => {
    render(<Button loading>Submit</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("is disabled when disabled prop set", () => {
    render(<Button disabled>Submit</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("calls onClick when clicked", async () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>Click</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("does not call onClick when disabled", async () => {
    const fn = vi.fn();
    render(<Button disabled onClick={fn}>Click</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).not.toHaveBeenCalled();
  });
});

// ============== Input ==============
import { Input } from "@/shared/components/Input";

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Email" />);
    expect(screen.getByLabelText("Email")).toBeDefined();
  });

  it("shows error message", () => {
    render(<Input error="Required field" />);
    expect(screen.getByText("Required field")).toBeDefined();
  });

  it("shows helper text when no error", () => {
    render(<Input helperText="Enter your email" />);
    expect(screen.getByText("Enter your email")).toBeDefined();
  });

  it("hides helper text when error present", () => {
    render(<Input helperText="Help text" error="Error!" />);
    expect(screen.queryByText("Help text")).toBeNull();
    expect(screen.getByText("Error!")).toBeDefined();
  });

  it("applies mono class when mono prop set", () => {
    const { container } = render(<Input mono />);
    const input = container.querySelector("input");
    expect(input?.className).toContain("font-mono");
  });
});

// ============== Badge ==============
import { Badge } from "@/shared/components/Badge";

describe("Badge", () => {
  it("renders text content", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("renders success variant", () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    expect(container.firstChild?.className).toContain("text-success-500");
  });

  it("renders dot indicator", () => {
    const { container } = render(<Badge dot>Status</Badge>);
    const dots = container.querySelectorAll(".rounded-full.h-1\\.5");
    expect(dots.length).toBeGreaterThan(0);
  });
});

// ============== Card ==============
import { Card, CardHeader, CardBody } from "@/shared/components/Card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card><CardBody>Content</CardBody></Card>);
    expect(screen.getByText("Content")).toBeDefined();
  });

  it("has hover class when hover prop set", () => {
    const { container } = render(<Card hover>Hoverable</Card>);
    expect(container.firstChild?.className).toContain("hover:shadow-glow");
  });

  it("renders with header and body", () => {
    render(
      <Card>
        <CardHeader>Title</CardHeader>
        <CardBody>Body</CardBody>
      </Card>
    );
    expect(screen.getByText("Title")).toBeDefined();
    expect(screen.getByText("Body")).toBeDefined();
  });
});

// ============== ProgressBar ==============
import { ProgressBar } from "@/shared/components/ProgressBar";

describe("ProgressBar", () => {
  it("renders label", () => {
    render(<ProgressBar value={50} label="Loading" />);
    expect(screen.getByText("Loading")).toBeDefined();
  });

  it("shows percentage", () => {
    render(<ProgressBar value={75} />);
    expect(screen.getByText("75%")).toBeDefined();
  });

  it("clamps percentage at 100", () => {
    render(<ProgressBar value={150} max={100} />);
    expect(screen.getByText("100%")).toBeDefined();
  });

  it("clamps percentage at 0", () => {
    render(<ProgressBar value={-10} />);
    expect(screen.getByText("0%")).toBeDefined();
  });
});

// ============== DataBadge ==============
import { DataBadge } from "@/shared/components/DataBadge";

describe("DataBadge", () => {
  it("renders the value", () => {
    render(<DataBadge value="test@example.com" type="email" />);
    expect(screen.getByText("test@example.com")).toBeDefined();
  });

  it("uses mono font", () => {
    const { container } = render(<DataBadge value="5261040828" type="nip" />);
    const btn = container.querySelector("button");
    expect(btn?.className).toContain("font-mono");
  });

  it("copies to clipboard on click", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<DataBadge value="copy-me" />);
    await userEvent.click(screen.getByText("copy-me"));
    expect(writeText).toHaveBeenCalledWith("copy-me");
  });
});

// ============== EmptyState ==============
import { EmptyState } from "@/shared/components/EmptyState";

describe("EmptyState", () => {
  it("renders title", () => {
    render(<EmptyState title="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeDefined();
  });

  it("renders description", () => {
    render(<EmptyState title="Empty" description="No data found" />);
    expect(screen.getByText("No data found")).toBeDefined();
  });

  it("renders action button", () => {
    render(<EmptyState title="Empty" action={<button>Create</button>} />);
    expect(screen.getByText("Create")).toBeDefined();
  });
});

// ============== OSINT Components ==============
import { ScanStatusBadge } from "@/shared/components/osint/ScanStatusBadge";
import { ConfidenceIndicator } from "@/shared/components/osint/ConfidenceIndicator";
import { NodeTypeIcon } from "@/shared/components/osint/NodeTypeIcon";

describe("ScanStatusBadge", () => {
  it("shows success status", () => {
    render(<ScanStatusBadge status="success" />);
    expect(screen.getByText("Success")).toBeDefined();
  });

  it("shows running with spinner", () => {
    const { container } = render(<ScanStatusBadge status="running" />);
    expect(screen.getByText("Running")).toBeDefined();
    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });
});

describe("ConfidenceIndicator", () => {
  it("shows percentage for high confidence", () => {
    render(<ConfidenceIndicator value={0.87} />);
    expect(screen.getByText("87%")).toBeDefined();
    expect(screen.getByText("High")).toBeDefined();
  });

  it("shows low label for low confidence", () => {
    render(<ConfidenceIndicator value={0.15} />);
    expect(screen.getByText("Low")).toBeDefined();
  });

  it("shows certain for very high confidence", () => {
    render(<ConfidenceIndicator value={0.98} />);
    expect(screen.getByText("Certain")).toBeDefined();
  });
});

describe("NodeTypeIcon", () => {
  it("renders without crashing for each type", () => {
    const types = ["person", "company", "email", "phone", "username", "ip", "domain"];
    types.forEach((type) => {
      const { container } = render(<NodeTypeIcon type={type} />);
      expect(container.querySelector("svg")).not.toBeNull();
    });
  });
});

// ============== InvestigationCard ==============
import { InvestigationCard } from "@/shared/components/osint/InvestigationCard";

describe("InvestigationCard", () => {
  it("renders title", () => {
    render(
      <TestWrapper>
        <InvestigationCard
          id="1" title="Test Investigation" status="draft"
          seedCount={2} tags={["test"]} createdAt="2024-01-01T00:00:00Z"
        />
      </TestWrapper>
    );
    expect(screen.getByText("Test Investigation")).toBeDefined();
  });

  it("shows status badge", () => {
    render(
      <TestWrapper>
        <InvestigationCard
          id="1" title="Test" status="running"
          seedCount={1} tags={[]} createdAt="2024-01-01T00:00:00Z"
        />
      </TestWrapper>
    );
    expect(screen.getByText("running")).toBeDefined();
  });
});
