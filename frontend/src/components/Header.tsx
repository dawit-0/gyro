import React from "react";
import { Task } from "../api";

interface Props {
  tasks: Task[];
  view: "tasks" | "assistants" | "taskflow";
  onViewChange: (view: "tasks" | "assistants" | "taskflow") => void;
  onNewTask: () => void;
  onNewAssistant: () => void;
}

export default function Header({ tasks, view, onViewChange, onNewTask, onNewAssistant }: Props) {
  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          GYRO
        </div>
        <div className="header-tabs">
          <button
            className={`header-tab${view === "tasks" ? " active" : ""}`}
            onClick={() => onViewChange("tasks")}
          >
            Tasks
          </button>
          <button
            className={`header-tab${view === "assistants" ? " active" : ""}`}
            onClick={() => onViewChange("assistants")}
          >
            Assistants
          </button>
          <button
            className={`header-tab${view === "taskflow" ? " active" : ""}`}
            onClick={() => onViewChange("taskflow")}
          >
            TaskFlow
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
        {view === "tasks" || view === "taskflow" ? (
          <button className="btn btn-primary" onClick={onNewTask}>
            + New Task
          </button>
        ) : (
          <button className="btn btn-primary" onClick={onNewAssistant}>
            + New Assistant
          </button>
        )}
      </div>
    </header>
  );
}
