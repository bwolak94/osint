import { useState } from "react";
import { Outlet, Navigate } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandPalette } from "./CommandPalette";
import { OnboardingTour } from "./OnboardingTour";
import { useAuthStore } from "@/features/auth/store";
import { useScanNotificationMonitor } from "@/features/pentesting/hooks/useScanNotificationMonitor";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { useChatPanel } from "@/features/chat/hooks";
import { MessageSquare } from "lucide-react";
import { LegalAcceptanceModal } from "@/features/legal/LegalAcceptanceModal";

export function Layout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('sidebar-collapsed') === 'true'
    } catch {
      return false
    }
  });
  const handleSidebarToggle = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      try { localStorage.setItem('sidebar-collapsed', String(next)) } catch { /* storage unavailable */ }
      return next
    })
  };
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const [tosAccepted, setTosAccepted] = useState(() => {
    try { return !!localStorage.getItem('tos_accepted_at') } catch { return false }
  });
  const { isOpen, toggle, close } = useChatPanel();
  useScanNotificationMonitor();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const needsToS = !tosAccepted && !user?.tos_accepted_at;

  return (
    <>
      {needsToS && <LegalAcceptanceModal onAccepted={() => setTosAccepted(true)} />}
      <div className="flex h-screen overflow-hidden" style={{ background: "var(--bg-base)" }}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={handleSidebarToggle}
        />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-6">
            <div className="mx-auto max-w-7xl">
              <Outlet />
            </div>
          </main>
        </div>
      </div>

      {/* Floating AI Agent button */}
      {!isOpen && (
        <button
          onClick={toggle}
          aria-label="Open AI Agent"
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full px-4 py-3 shadow-lg transition-all hover:scale-105 active:scale-95"
          style={{ background: "var(--brand-500)", color: "white" }}
        >
          <MessageSquare className="h-5 w-5" />
          <span className="text-sm font-medium">AI Agent</span>
        </button>
      )}

      <ChatPanel isOpen={isOpen} onClose={close} />

      <CommandPalette />
      <OnboardingTour />
    </>
  );
}
