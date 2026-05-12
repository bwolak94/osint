/**
 * Hub feature tests — store, hooks, and component rendering.
 *
 * Uses Vitest + Testing Library. API calls are mocked with vi.mock;
 * no MSW needed for pure-unit coverage.
 */

import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act } from "@testing-library/react";
import { render, screen, fireEvent } from "@testing-library/react";

// ── Store ─────────────────────────────────────────────────────────────────────

import { useHubStore } from "../store";

describe("useHubStore", () => {
  beforeEach(() => {
    useHubStore.getState().reset();
  });

  it("initialises with idle status and no task", () => {
    const s = useHubStore.getState();
    expect(s.status).toBe("idle");
    expect(s.taskId).toBeNull();
    expect(s.thoughts).toEqual([]);
    expect(s.result).toBeNull();
    expect(s.error).toBeNull();
  });

  it("startTask sets taskId, streamUrl, and queued status", () => {
    act(() => {
      useHubStore.getState().startTask("t-1", "/ws/t-1");
    });
    const s = useHubStore.getState();
    expect(s.taskId).toBe("t-1");
    expect(s.streamUrl).toBe("/ws/t-1");
    expect(s.status).toBe("queued");
    expect(s.thoughts).toEqual([]);
  });

  it("appendThought adds to thoughts list in order", () => {
    act(() => {
      useHubStore.getState().appendThought("first");
      useHubStore.getState().appendThought("second");
    });
    expect(useHubStore.getState().thoughts).toEqual(["first", "second"]);
  });

  it("setStatus updates status", () => {
    act(() => useHubStore.getState().setStatus("running"));
    expect(useHubStore.getState().status).toBe("running");
  });

  it("setResult with result sets completed", () => {
    act(() => useHubStore.getState().setResult("done!", null));
    const s = useHubStore.getState();
    expect(s.result).toBe("done!");
    expect(s.status).toBe("completed");
    expect(s.error).toBeNull();
  });

  it("setResult with error sets failed", () => {
    act(() => useHubStore.getState().setResult(null, "oops"));
    const s = useHubStore.getState();
    expect(s.error).toBe("oops");
    expect(s.status).toBe("failed");
  });

  it("reset returns to initial state", () => {
    act(() => {
      useHubStore.getState().startTask("t-2", "/ws");
      useHubStore.getState().appendThought("thought");
      useHubStore.getState().reset();
    });
    const s = useHubStore.getState();
    expect(s.taskId).toBeNull();
    expect(s.thoughts).toEqual([]);
    expect(s.status).toBe("idle");
  });
});

// ── ModuleSelector ────────────────────────────────────────────────────────────

import { ModuleSelector } from "../components/ModuleSelector";

describe("ModuleSelector", () => {
  it("renders all five module tabs", () => {
    render(
      <ModuleSelector value="chat" onChange={() => undefined} />,
    );
    expect(screen.getByRole("tab", { name: /chat/i })).toBeDefined();
    expect(screen.getByRole("tab", { name: /news/i })).toBeDefined();
    expect(screen.getByRole("tab", { name: /tasks/i })).toBeDefined();
    expect(screen.getByRole("tab", { name: /knowledge/i })).toBeDefined();
    expect(screen.getByRole("tab", { name: /calendar/i })).toBeDefined();
  });

  it("marks the active tab as selected", () => {
    render(<ModuleSelector value="news" onChange={() => undefined} />);
    const newsTab = screen.getByRole("tab", { name: /news/i });
    expect(newsTab.getAttribute("aria-selected")).toBe("true");
    const chatTab = screen.getByRole("tab", { name: /chat/i });
    expect(chatTab.getAttribute("aria-selected")).toBe("false");
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = vi.fn();
    render(<ModuleSelector value="chat" onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: /tasks/i }));
    expect(onChange).toHaveBeenCalledWith("tasks");
  });

  it("disables all tabs when disabled=true", () => {
    render(<ModuleSelector value="chat" onChange={() => undefined} disabled />);
    const tabs = screen.getAllByRole("tab");
    tabs.forEach((tab) => {
      expect((tab as HTMLButtonElement).disabled).toBe(true);
    });
  });
});

// ── HubQueryInput ─────────────────────────────────────────────────────────────

import { HubQueryInput } from "../components/HubQueryInput";

describe("HubQueryInput", () => {
  it("renders textarea and send button", () => {
    render(
      <HubQueryInput value="" onChange={() => undefined} onSubmit={() => undefined} />,
    );
    expect(screen.getByRole("textbox")).toBeDefined();
    expect(screen.getByRole("button", { name: /send/i })).toBeDefined();
  });

  it("calls onChange on input", () => {
    const onChange = vi.fn();
    render(
      <HubQueryInput value="" onChange={onChange} onSubmit={() => undefined} />,
    );
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
    expect(onChange).toHaveBeenCalledWith("hello");
  });

  it("calls onSubmit on Enter key", () => {
    const onSubmit = vi.fn();
    render(
      <HubQueryInput value="query" onChange={() => undefined} onSubmit={onSubmit} />,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(onSubmit).toHaveBeenCalled();
  });

  it("does NOT submit on Shift+Enter", () => {
    const onSubmit = vi.fn();
    render(
      <HubQueryInput value="query" onChange={() => undefined} onSubmit={onSubmit} />,
    );
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disables textarea and button when disabled=true", () => {
    render(
      <HubQueryInput
        value="q"
        onChange={() => undefined}
        onSubmit={() => undefined}
        disabled
      />,
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /send/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});

// ── AgentThinkingStream ───────────────────────────────────────────────────────

import { AgentThinkingStream } from "../components/AgentThinkingStream";

describe("AgentThinkingStream", () => {
  it("renders nothing visible when idle with no thoughts", () => {
    const { container } = render(
      <AgentThinkingStream thoughts={[]} status="idle" />,
    );
    // Status label should be present
    expect(screen.getByText("Idle")).toBeDefined();
    // No thought list items
    expect(container.querySelectorAll("li")).toHaveLength(0);
  });

  it("renders thoughts as ordered list items", () => {
    render(
      <AgentThinkingStream
        thoughts={["First thought", "Second thought"]}
        status="running"
      />,
    );
    expect(screen.getByText("First thought")).toBeDefined();
    expect(screen.getByText("Second thought")).toBeDefined();
  });

  it("shows pulse indicator while running", () => {
    const { container } = render(
      <AgentThinkingStream thoughts={[]} status="running" />,
    );
    // Pulse span is aria-hidden, find by class
    const pulse = container.querySelector(".animate-pulse");
    expect(pulse).not.toBeNull();
  });

  it("shows 'Starting agent pipeline…' placeholder when running with no thoughts", () => {
    render(<AgentThinkingStream thoughts={[]} status="running" />);
    expect(screen.getByText(/starting agent pipeline/i)).toBeDefined();
  });
});

// ── HitlApprovalCard ──────────────────────────────────────────────────────────

import { HitlApprovalCard } from "../components/HitlApprovalCard";

describe("HitlApprovalCard", () => {
  it("renders the query in a blockquote", () => {
    render(
      <HitlApprovalCard
        query="delete all my tasks"
        onApprove={() => undefined}
        onReject={() => undefined}
      />,
    );
    expect(screen.getByText("delete all my tasks")).toBeDefined();
  });

  it("calls onApprove when Approve is clicked", () => {
    const onApprove = vi.fn();
    render(
      <HitlApprovalCard
        query="q"
        onApprove={onApprove}
        onReject={() => undefined}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprove).toHaveBeenCalled();
  });

  it("calls onReject when Reject is clicked", () => {
    const onReject = vi.fn();
    render(
      <HitlApprovalCard
        query="q"
        onApprove={() => undefined}
        onReject={onReject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalled();
  });

  it("disables buttons when isPending=true", () => {
    render(
      <HitlApprovalCard
        query="q"
        onApprove={() => undefined}
        onReject={() => undefined}
        isPending
      />,
    );
    expect((screen.getByRole("button", { name: /approve/i }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: /reject/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});

// ── TaskList ──────────────────────────────────────────────────────────────────

import { TaskList } from "../components/TaskList";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/shared/api/client", () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { tasks: [], total: 0 } }),
    post: vi.fn().mockResolvedValue({ data: { id: "t1", title: "New task", status: "todo", priority: 3, source: "manual", created_at: new Date().toISOString(), description: null, due_at: null } }),
    delete: vi.fn().mockResolvedValue({}),
  },
}));

function makeQueryWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("TaskList", () => {
  it("renders task input and create button", () => {
    render(<TaskList />, { wrapper: makeQueryWrapper() });
    expect(screen.getByRole("textbox")).toBeDefined();
    // The create button is an icon button (Plus icon), find by aria-label
    expect(screen.getByRole("button", { name: /create/i })).toBeDefined();
  });

  it("renders filter buttons: All, todo, in_progress, done", () => {
    render(<TaskList />, { wrapper: makeQueryWrapper() });
    expect(screen.getByRole("button", { name: /all/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /status_todo/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /status_done/i })).toBeDefined();
  });

  it("shows no_tasks message when task list is empty and loaded", async () => {
    render(<TaskList />, { wrapper: makeQueryWrapper() });
    // Wait for query to settle
    await screen.findByText("no_tasks");
  });
});

// ── KnowledgePanel ────────────────────────────────────────────────────────────

import { KnowledgePanel } from "../components/KnowledgePanel";

describe("KnowledgePanel", () => {
  it("renders upload button and url input", () => {
    render(<KnowledgePanel />, { wrapper: makeQueryWrapper() });
    expect(screen.getByRole("button", { name: /upload_label/i })).toBeDefined();
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("renders ingest button for URL", () => {
    render(<KnowledgePanel />, { wrapper: makeQueryWrapper() });
    expect(screen.getByRole("button", { name: /ingest_button/i })).toBeDefined();
  });

  it("disables ingest button when url is empty", () => {
    render(<KnowledgePanel />, { wrapper: makeQueryWrapper() });
    const btn = screen.getByRole("button", { name: /ingest_button/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it("enables ingest button when url has value", () => {
    render(<KnowledgePanel />, { wrapper: makeQueryWrapper() });
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "https://example.com" } });
    const btn = screen.getByRole("button", { name: /ingest_button/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });
});

// ── AgentResultPanel ──────────────────────────────────────────────────────────

import { AgentResultPanel } from "../components/AgentResultPanel";

describe("AgentResultPanel", () => {
  it("renders nothing when result and error are both null", () => {
    const { container } = render(
      <AgentResultPanel result={null} error={null} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders result text with 'Result' heading", () => {
    render(<AgentResultPanel result="Here is your answer." error={null} />);
    expect(screen.getByText("Result")).toBeDefined();
    expect(screen.getByText("Here is your answer.")).toBeDefined();
  });

  it("renders error text with 'Error' heading", () => {
    render(<AgentResultPanel result={null} error="Something went wrong." />);
    expect(screen.getByText("Error")).toBeDefined();
    expect(screen.getByText("Something went wrong.")).toBeDefined();
  });
});
