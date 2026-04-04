import React, { useEffect, useState } from "react";
import { api, DebugStatus, Task } from "../api";

interface Props {
  tasks: Task[];
  view: "flows" | "agents";
  onViewChange: (view: "flows" | "agents") => void;
  onNewFlow: () => void;
  onNewAgent: () => void;
  onQuickTask: () => void;
}

export default function Header({ tasks, view, onViewChange, onNewFlow, onNewAgent, onQuickTask }: Props) {
  const [debugStatus, setDebugStatus] = useState<DebugStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const s = await api.debug.status();
        if (!cancelled) setDebugStatus(s);
      } catch {
        if (!cancelled) setDebugStatus(null);
      }
    }
    poll();
    const interval = setInterval(poll, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          GYRO
        </div>
        <div className="header-tabs">
          <button
            className={`header-tab${view === "flows" ? " active" : ""}`}
            onClick={() => onViewChange("flows")}
          >
            Flows
          </button>
          <button
            className={`header-tab${view === "agents" ? " active" : ""}`}
            onClick={() => onViewChange("agents")}
          >
            Agent Registry
          </button>
        </div>
      </div>
      <div className="header-stats">
        <span className="stat-badge">
          {tasks.length} task{tasks.length !== 1 ? "s" : ""}
        </span>
        {tasks.filter((t) => t.schedule).length > 0 && (
          <span className="stat-badge">
            <span className="dot scheduled" /> {tasks.filter((t) => t.schedule).length} scheduled
          </span>
        )}
      </div>
      <div className="header-system-status">
        {debugStatus ? (
          <>
            <span className={`system-status-dot ${debugStatus.orchestrator.running ? "ok" : "down"}`} />
            <span className="system-status-text">
              {debugStatus.orchestrator.active_runs} active &middot; {debugStatus.queued_runs} queued
            </span>
            {debugStatus.recent_failures.length > 0 && (
              <span className="system-status-warn">
                {debugStatus.recent_failures.length} recent failure{debugStatus.recent_failures.length !== 1 ? "s" : ""}
              </span>
            )}
          </>
        ) : (
          <>
            <span className="system-status-dot down" />
            <span className="system-status-text">Status unavailable</span>
          </>
        )}
      </div>
      <div className="header-actions">
        {view === "flows" ? (
          <>
            <button className="btn btn-secondary" onClick={onQuickTask}>
              + Quick Task
            </button>
            <button className="btn btn-primary" onClick={onNewFlow}>
              + New Flow
            </button>
          </>
        ) : (
          <button className="btn btn-primary" onClick={onNewAgent}>
            + New Agent
          </button>
        )}
      </div>
    </header>
  );
}
