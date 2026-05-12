export { HubPage } from "./HubPage";
export { useHubStore } from "./store";
export { SynergySuggestionCard } from "./components/SynergySuggestionCard";

// Phase 3 — Cognitive Load & UI Themes
export { useThemeStore } from "./stores/themeStore";
export { ThemeToggle } from "./components/ThemeToggle";
export { FocusTimer } from "./components/FocusTimer";
export { EnergyHeatmap } from "./components/EnergyHeatmap";
export { useThemeShortcut } from "./hooks/useThemeShortcut";

export type { HubTheme } from "./stores/themeStore";
export type { EnergyHeatmapProps } from "./components/EnergyHeatmap";
export type { FocusTimerProps } from "./components/FocusTimer";

export type {
  HubModule,
  AgentStatus,
  AgentRunRequest,
  AgentRunResponse,
  SynergyChain,
  TaskModificationProposal,
  CalendarAdjustmentProposal,
} from "./types";
