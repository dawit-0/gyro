import React from "react";
import { Task } from "../api";

interface Props {
  tasks: Task[];
  view: "flows" | "assistants";
  onViewChange: (view: "flows" | "assistants") => void;
  onNewFlow: () => void;
  onNewAssistant: () => void;
  onQuickTask: () => void;
}

export default function Header({ tasks, view, onViewChange, onNewFlow, onNewAssistant, onQuickTask }: Props) {
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
            className={`header-tab${view === "assistants" ? " active" : ""}`}
            onClick={() => onViewChange("assistants")}
          >
            Assistants
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
          <button className="btn btn-primary" onClick={onNewAssistant}>
            + New Assistant
          </button>
        )}
      </div>
    </header>
  );
}
