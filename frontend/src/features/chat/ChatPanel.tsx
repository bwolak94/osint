import { useState, useRef, useEffect, useCallback, useId } from "react";
import {
  Send, Bot, User, X, MessageSquare, Loader2,
  Search, Shield, ListChecks, CheckCircle2, AlertCircle,
  ChevronDown, ChevronRight, Maximize2, Minimize2,
} from "lucide-react";
import { useAuthStore } from "@/features/auth/store";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ToolCall {
  tool_id: string;
  tool: string;
  input?: Record<string, unknown>;
  result?: Record<string, unknown>;
  status: "running" | "done" | "error";
}

type MessagePart =
  | { kind: "text"; content: string }
  | { kind: "tool_call"; toolCall: ToolCall };

interface Message {
  id: string;
  role: "user" | "assistant";
  parts: MessagePart[];
  timestamp: Date;
}

interface ChatPanelProps {
  investigationContext?: string;
  isOpen: boolean;
  onClose: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tool metadata
// ─────────────────────────────────────────────────────────────────────────────

const TOOL_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  run_osint_scan:       { label: "OSINT Scan",        icon: <Search className="h-3.5 w-3.5" />,    color: "#3b82f6" },
  run_port_scan:        { label: "Port Scan",          icon: <Shield className="h-3.5 w-3.5" />,    color: "#f59e0b" },
  get_scan_results:     { label: "Fetching Results",   icon: <ListChecks className="h-3.5 w-3.5" />, color: "#8b5cf6" },
  list_recent_activity: { label: "Recent Activity",    icon: <ListChecks className="h-3.5 w-3.5" />, color: "#6b7280" },
  get_pentest_findings: { label: "Pentest Findings",   icon: <AlertCircle className="h-3.5 w-3.5" />, color: "#ef4444" },
};

// ─────────────────────────────────────────────────────────────────────────────
// ToolCallCard component
// ─────────────────────────────────────────────────────────────────────────────

function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const meta = TOOL_META[toolCall.tool] ?? { label: toolCall.tool, icon: <Bot className="h-3.5 w-3.5" />, color: "#6b7280" };

  return (
    <div
      className="rounded-md border text-xs overflow-hidden"
      style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}
    >
      <button
        className="flex w-full items-center gap-2 px-3 py-2 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className="flex items-center justify-center rounded-full p-1" style={{ background: meta.color + "22", color: meta.color }}>
          {meta.icon}
        </span>
        <span className="flex-1 font-medium" style={{ color: "var(--text-primary)" }}>
          {meta.label}
        </span>
        {toolCall.status === "running" && (
          <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: meta.color }} />
        )}
        {toolCall.status === "done" && (
          <CheckCircle2 className="h-3.5 w-3.5" style={{ color: "#22c55e" }} />
        )}
        {toolCall.status === "error" && (
          <AlertCircle className="h-3.5 w-3.5" style={{ color: "#ef4444" }} />
        )}
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 ml-1" style={{ color: "var(--text-tertiary)" }} />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 ml-1" style={{ color: "var(--text-tertiary)" }} />
        )}
      </button>

      {expanded && (
        <div className="border-t px-3 py-2 space-y-2" style={{ borderColor: "var(--border-subtle)" }}>
          {toolCall.input && (
            <div>
              <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>Input</p>
              <pre
                className="rounded p-2 text-xs overflow-x-auto"
                style={{ background: "var(--bg-base)", color: "var(--text-secondary)", fontFamily: "monospace" }}
              >
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
          )}
          {toolCall.result && (
            <div>
              <p className="text-xs font-medium mb-1" style={{ color: "var(--text-tertiary)" }}>Result</p>
              <pre
                className="rounded p-2 text-xs overflow-x-auto max-h-40"
                style={{ background: "var(--bg-base)", color: "var(--text-secondary)", fontFamily: "monospace" }}
              >
                {JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Message rendering
// ─────────────────────────────────────────────────────────────────────────────

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-2 ${isUser ? "justify-end" : "items-start"}`}>
      {!isUser && (
        <div className="mt-1 shrink-0 rounded-full p-1.5" style={{ background: "var(--brand-900)" }}>
          <Bot className="h-3 w-3" style={{ color: "var(--brand-400)" }} />
        </div>
      )}

      <div className={`flex flex-col gap-2 ${isUser ? "items-end" : "items-start"} max-w-[90%]`}>
        {message.parts.map((part, i) => {
          if (part.kind === "text") {
            if (!part.content) return null;
            return (
              <div
                key={i}
                className="rounded-lg px-3 py-2 text-sm"
                style={{
                  background: isUser ? "var(--brand-500)" : "var(--bg-overlay)",
                  color: isUser ? "white" : "var(--text-primary)",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {part.content}
              </div>
            );
          }
          if (part.kind === "tool_call") {
            return <ToolCallCard key={i} toolCall={part.toolCall} />;
          }
          return null;
        })}
      </div>

      {isUser && (
        <div className="mt-1 shrink-0 rounded-full p-1.5" style={{ background: "var(--bg-overlay)" }}>
          <User className="h-3 w-3" style={{ color: "var(--text-secondary)" }} />
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main ChatPanel
// ─────────────────────────────────────────────────────────────────────────────

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  parts: [{
    kind: "text",
    content:
      "Hi! I'm your AI security assistant. I can run scans, investigate targets, and analyze findings — all from chat.\n\n" +
      "**Try asking:**\n" +
      "• `Run OSINT check for email: example@example.com`\n" +
      "• `Do a full port scan on google.pl`\n" +
      "• `Show my recent investigations`\n" +
      "• `Check what's running on 192.168.1.1`",
  }],
  timestamp: new Date(),
};

export function ChatPanel({ isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const titleId = useId();

  const { accessToken } = useAuthStore();

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);
  useEffect(() => { if (isOpen) inputRef.current?.focus(); }, [isOpen]);

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      parts: [{ kind: "text", content: trimmed }],
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsStreaming(true);

    const assistantId = crypto.randomUUID();
    const emptyAssistant: Message = {
      id: assistantId,
      role: "assistant",
      parts: [],
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, emptyAssistant]);

    // Helper to update the live assistant message
    const updateAssistant = (updater: (parts: MessagePart[]) => MessagePart[]) => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, parts: updater(m.parts) } : m
        )
      );
    };

    // Build conversation history (exclude welcome message)
    const history = [...messages, userMsg]
      .filter((m) => m.id !== "welcome")
      .map((m) => ({
        role: m.role,
        content: m.parts
          .filter((p) => p.kind === "text")
          .map((p) => (p as { kind: "text"; content: string }).content)
          .join(""),
      }))
      .filter((m) => m.content.length > 0);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const resp = await fetch("/api/v1/agent/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ messages: history }),
        signal: ctrl.signal,
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Track tool calls by tool_id
      const toolCallMap = new Map<string, ToolCall>();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let evt: Record<string, unknown>;
          try { evt = JSON.parse(raw); } catch { continue; }

          const type = evt.type as string;

          if (type === "text_delta") {
            const token = evt.content as string;
            updateAssistant((parts) => {
              const last = parts[parts.length - 1];
              if (last?.kind === "text") {
                return [...parts.slice(0, -1), { kind: "text", content: last.content + token }];
              }
              return [...parts, { kind: "text", content: token }];
            });
          }

          else if (type === "tool_start") {
            const tc: ToolCall = {
              tool_id: evt.tool_id as string,
              tool: evt.tool as string,
              status: "running",
            };
            toolCallMap.set(tc.tool_id, tc);
            updateAssistant((parts) => [...parts, { kind: "tool_call", toolCall: { ...tc } }]);
          }

          else if (type === "tool_input") {
            const tc = toolCallMap.get(evt.tool_id as string);
            if (tc) {
              tc.input = evt.input as Record<string, unknown>;
              toolCallMap.set(tc.tool_id, tc);
              updateAssistant((parts) =>
                parts.map((p) =>
                  p.kind === "tool_call" && p.toolCall.tool_id === tc.tool_id
                    ? { ...p, toolCall: { ...tc } }
                    : p
                )
              );
            }
          }

          else if (type === "tool_result") {
            const tc = toolCallMap.get(evt.tool_id as string);
            if (tc) {
              const result = evt.result as Record<string, unknown>;
              const hasError = "error" in result;
              tc.result = result;
              tc.status = hasError ? "error" : "done";
              toolCallMap.set(tc.tool_id, tc);
              updateAssistant((parts) =>
                parts.map((p) =>
                  p.kind === "tool_call" && p.toolCall.tool_id === tc.tool_id
                    ? { ...p, toolCall: { ...tc } }
                    : p
                )
              );
            }
          }

          else if (type === "error") {
            updateAssistant((parts) => [
              ...parts,
              { kind: "text", content: `⚠️ ${evt.content as string}` },
            ]);
          }

          else if (type === "done") {
            break;
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        updateAssistant((parts) => [
          ...parts,
          { kind: "text", content: "Sorry, I encountered an error. Please try again." },
        ]);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [input, isStreaming, messages, accessToken]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setIsStreaming(false);
  };

  if (!isOpen) return null;

  const panelWidth = expanded ? 640 : 420;
  const panelHeight = expanded ? "80vh" : 580;

  return (
    <div
      role="dialog"
      aria-labelledby={titleId}
      aria-modal="false"
      className="fixed bottom-4 right-4 z-50 flex flex-col rounded-xl border shadow-2xl"
      style={{
        width: panelWidth,
        height: panelHeight,
        background: "var(--bg-surface)",
        borderColor: "var(--border-default)",
        transition: "width 0.2s ease, height 0.2s ease",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between rounded-t-xl border-b px-4 py-3 shrink-0"
        style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}
      >
        <div className="flex items-center gap-2">
          <div className="rounded-full p-1.5" style={{ background: "var(--brand-900)" }}>
            <MessageSquare className="h-3.5 w-3.5" style={{ color: "var(--brand-400)" }} />
          </div>
          <span id={titleId} className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            AI Agent
          </span>
          <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ background: "var(--brand-900)", color: "var(--brand-400)" }}>
            Claude
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="rounded p-1.5 transition-colors hover:bg-bg-overlay"
            aria-label={expanded ? "Shrink panel" : "Expand panel"}
          >
            {expanded ? (
              <Minimize2 className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
            ) : (
              <Maximize2 className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
            )}
          </button>
          <button
            onClick={onClose}
            className="rounded p-1.5 transition-colors hover:bg-bg-overlay"
            aria-label="Close chat"
          >
            <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isStreaming && (
          <div className="flex gap-2 items-start">
            <div className="mt-1 shrink-0 rounded-full p-1.5" style={{ background: "var(--brand-900)" }}>
              <Bot className="h-3 w-3" style={{ color: "var(--brand-400)" }} />
            </div>
            <div className="rounded-lg px-3 py-2 flex items-center gap-2" style={{ background: "var(--bg-overlay)" }}>
              <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: "var(--text-tertiary)" }} />
              <span className="text-xs" style={{ color: "var(--text-tertiary)" }}>Thinking…</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested prompts (shown only when no conversation yet) */}
      {messages.length === 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-2">
          {[
            "Show recent activity",
            "Scan IP 8.8.8.8",
            "Port scan google.pl",
          ].map((prompt) => (
            <button
              key={prompt}
              onClick={() => { setInput(prompt); inputRef.current?.focus(); }}
              className="rounded-full border px-3 py-1 text-xs transition-colors hover:bg-bg-overlay"
              style={{ borderColor: "var(--border-subtle)", color: "var(--text-secondary)" }}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="border-t p-3 shrink-0" style={{ borderColor: "var(--border-subtle)" }}>
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything — scan an email, run a port scan, get findings…"
            rows={1}
            className="flex-1 resize-none rounded-lg border px-3 py-2 text-sm"
            style={{
              borderColor: "var(--border-default)",
              background: "var(--bg-base)",
              color: "var(--text-primary)",
              maxHeight: 120,
              lineHeight: "1.5",
            }}
          />
          {isStreaming ? (
            <button
              onClick={handleStop}
              className="rounded-lg px-3 py-2 transition-colors shrink-0"
              style={{ background: "#ef4444", color: "white" }}
              aria-label="Stop generation"
            >
              <X className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="rounded-lg px-3 py-2 transition-colors disabled:opacity-40 shrink-0"
              style={{ background: "var(--brand-500)", color: "white" }}
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
        <p className="mt-1.5 text-xs" style={{ color: "var(--text-tertiary)" }}>
          Enter to send · Shift+Enter for new line · Esc to close
        </p>
      </div>
    </div>
  );
}
