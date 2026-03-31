import React from "react";
import { Job } from "../api";

interface Props {
  jobs: Job[];
  view: "jobs" | "assistants";
  onViewChange: (view: "jobs" | "assistants") => void;
  onNewJob: () => void;
  onNewAssistant: () => void;
}

export default function Header({ jobs, view, onViewChange, onNewJob, onNewAssistant }: Props) {
  const running = jobs.filter((j) => j.status === "running").length;
  const queued = jobs.filter((j) => j.status === "queued").length;
  const done = jobs.filter((j) => j.status === "done").length;
  const failed = jobs.filter((j) => j.status === "failed").length;

  return (
    <header className="header">
      <div className="header-left">
        <div className="header-logo">
          GYRO
        </div>
        <div className="header-tabs">
          <button
            className={`header-tab${view === "jobs" ? " active" : ""}`}
            onClick={() => onViewChange("jobs")}
          >
            Jobs
          </button>
          <button
            className={`header-tab${view === "assistants" ? " active" : ""}`}
            onClick={() => onViewChange("assistants")}
          >
            Assistants
          </button>
        </div>
      </div>
      {view === "jobs" && (
        <div className="header-stats">
          {running > 0 && (
            <span className="stat-badge">
              <span className="dot running" /> {running} running
            </span>
          )}
          {queued > 0 && (
            <span className="stat-badge">
              <span className="dot queued" /> {queued} queued
            </span>
          )}
          <span className="stat-badge">
            <span className="dot done" /> {done} done
          </span>
          {failed > 0 && (
            <span className="stat-badge">
              <span className="dot failed" /> {failed} failed
            </span>
          )}
        </div>
      )}
      <div className="header-actions">
        {view === "jobs" ? (
          <button className="btn btn-primary" onClick={onNewJob}>
            + New Job
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
