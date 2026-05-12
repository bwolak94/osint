import { useCallback, useEffect, useRef, useState } from "react";
import { useThemeStore } from "../stores/themeStore";

export interface FocusTimerProps {
  /** Total session duration in seconds. Defaults to 25 minutes (1500 s). */
  durationSeconds?: number;
  onComplete?: () => void;
}

const DEFAULT_DURATION = 25 * 60; // 1500 seconds

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

/** SVG progress ring parameters */
const RADIUS = 40;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function FocusTimer({
  durationSeconds = DEFAULT_DURATION,
  onComplete,
}: FocusTimerProps) {
  const theme = useThemeStore((s) => s.theme);
  const isDeepWork = theme === "deep-work";

  const [secondsLeft, setSecondsLeft] = useState(durationSeconds);
  const [isRunning, setIsRunning] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  // Keep onComplete stable across renders
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Reset when durationSeconds prop changes
  useEffect(() => {
    setSecondsLeft(durationSeconds);
    setIsRunning(false);
    setIsComplete(false);
  }, [durationSeconds]);

  useEffect(() => {
    if (!isRunning) return;

    const id = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(id);
          setIsRunning(false);
          setIsComplete(true);
          onCompleteRef.current?.();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(id);
  }, [isRunning]);

  const handleStartPause = useCallback(() => {
    if (isComplete) return;
    setIsRunning((r) => !r);
  }, [isComplete]);

  const handleReset = useCallback(() => {
    setIsRunning(false);
    setIsComplete(false);
    setSecondsLeft(durationSeconds);
  }, [durationSeconds]);

  // Only render in deep-work mode
  if (!isDeepWork) return null;

  const progress = (durationSeconds - secondsLeft) / durationSeconds;
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  return (
    <div
      className="flex flex-col items-center gap-4 rounded-xl p-4"
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border-default)",
        boxShadow: "var(--shadow-glow)",
      }}
      role="region"
      aria-label="Focus timer"
    >
      {/* SVG progress ring */}
      <svg
        width="100"
        height="100"
        viewBox="0 0 100 100"
        aria-hidden="true"
        className="rotate-[-90deg]"
      >
        {/* Track */}
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="var(--border-default)"
          strokeWidth="8"
        />
        {/* Progress arc */}
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="var(--brand-500)"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
      </svg>

      {/* Timer display */}
      <div
        className="font-mono text-3xl font-semibold tabular-nums"
        style={{ color: "var(--text-primary)", marginTop: "-6.5rem" }}
        aria-live="polite"
        aria-atomic="true"
        aria-label={`Time remaining: ${formatTime(secondsLeft)}`}
      >
        {isComplete ? (
          <span style={{ color: "var(--brand-500)", fontSize: "1rem" }}>
            Break time!
          </span>
        ) : (
          formatTime(secondsLeft)
        )}
      </div>

      {/* Spacer to clear the SVG overlap */}
      <div style={{ marginTop: "4.5rem" }} />

      {/* Controls */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleStartPause}
          disabled={isComplete}
          className="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors disabled:opacity-40"
          style={{
            background: "var(--brand-500)",
            color: "#fff",
          }}
          aria-label={isRunning ? "Pause timer" : "Start timer"}
        >
          {isRunning ? "Pause" : "Start"}
        </button>

        <button
          type="button"
          onClick={handleReset}
          className="rounded-lg px-4 py-1.5 text-sm font-medium transition-colors"
          style={{
            background: "var(--bg-elevated)",
            color: "var(--text-secondary)",
            border: "1px solid var(--border-default)",
          }}
          aria-label="Reset timer"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
