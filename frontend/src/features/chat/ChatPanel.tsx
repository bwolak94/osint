import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, X, MessageSquare, Loader2 } from "lucide-react";
import { apiClient } from "@/shared/api/client";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatPanelProps {
  investigationContext?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function ChatPanel({ investigationContext, isOpen, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "I'm your OSINT analysis assistant. Ask me about investigation strategies, analyze findings, or get help interpreting results.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const chatMessages = [...messages, userMessage]
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content }));

      const resp = await apiClient.post<{ content: string }>("/chat", {
        messages: chatMessages,
        investigation_context: investigationContext || "",
        stream: false,
      });

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: resp.data.content,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col rounded-lg border shadow-xl"
      style={{
        width: 400,
        height: 560,
        background: "var(--bg-surface)",
        borderColor: "var(--border-default)",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between rounded-t-lg border-b px-4 py-3"
        style={{ borderColor: "var(--border-subtle)", background: "var(--bg-elevated)" }}
      >
        <div className="flex items-center gap-2">
          <MessageSquare className="h-4 w-4" style={{ color: "var(--brand-400)" }} />
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            AI Assistant
          </span>
        </div>
        <button onClick={onClose} className="rounded p-1 transition-colors hover:bg-bg-overlay">
          <X className="h-4 w-4" style={{ color: "var(--text-secondary)" }} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : ""}`}>
            {msg.role === "assistant" && (
              <div className="shrink-0 rounded-full p-1.5" style={{ background: "var(--brand-900)" }}>
                <Bot className="h-3 w-3" style={{ color: "var(--brand-400)" }} />
              </div>
            )}
            <div
              className="max-w-[85%] rounded-lg px-3 py-2 text-sm"
              style={{
                background: msg.role === "user" ? "var(--brand-500)" : "var(--bg-overlay)",
                color: msg.role === "user" ? "white" : "var(--text-primary)",
              }}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
            {msg.role === "user" && (
              <div className="shrink-0 rounded-full p-1.5" style={{ background: "var(--bg-overlay)" }}>
                <User className="h-3 w-3" style={{ color: "var(--text-secondary)" }} />
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-2">
            <div className="shrink-0 rounded-full p-1.5" style={{ background: "var(--brand-900)" }}>
              <Bot className="h-3 w-3" style={{ color: "var(--brand-400)" }} />
            </div>
            <div className="rounded-lg px-3 py-2" style={{ background: "var(--bg-overlay)" }}>
              <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--text-tertiary)" }} />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-3" style={{ borderColor: "var(--border-subtle)" }}>
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your investigation..."
            rows={1}
            className="flex-1 resize-none rounded-md border px-3 py-2 text-sm"
            style={{
              borderColor: "var(--border-default)",
              background: "var(--bg-base)",
              color: "var(--text-primary)",
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="rounded-md px-3 py-2 transition-colors disabled:opacity-50"
            style={{ background: "var(--brand-500)", color: "white" }}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
