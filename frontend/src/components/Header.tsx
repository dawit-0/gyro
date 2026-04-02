import React from "react";
import { Job } from "../api";

interface Props {
  jobs: Job[];
  view: "jobs" | "assistants" | "schedules" | "agentflow";
  onViewChange: (view: "jobs" | "assistants" | "schedules" | "agentflow") => void;
  onNewJob: () => void;
  onNewAssistant: () => void;
  onNewSchedule: () => void;
}

export default function Header({ jobs, view, onViewChange, onNewJob, onNewAssistant, onNewSchedule }: Props) {
  const running = jobs.filter((j) => j.status === "running").length;
  const queued = jobs.filter((j) => j.status === "queued").length;
  const done = jobs.filter((j) => j.status === "done").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const scheduled = jobs.filter(
    (j) => j.status === "queued" && j.scheduled_for && new Date(j.scheduled_for) > new Date()
  ).length;

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
          <button
            className={`header-tab${view === "agentflow" ? " active" : ""}`}
            onClick={() => onViewChange("agentflow")}
          >
            AgentFlow
          </button>
          <button
            className={`header-tab${view === "schedules" ? " active" : ""}`}
            onClick={() => onViewChange("schedules")}
          >
            Schedules
          </button>
        </div>
      </div>
      {(view === "jobs" || view === "agentflow") && (
        <div className="header-stats">
          {running > 0 && (
            <span className="stat-badge">
              <span className="dot running" /> {running} running
            </span>
          )}
          {queued > 0 && (
            <span className="stat-badge">
              <span className="dot queued" /> {queued - scheduled} queued
            </span>
          )}
          {scheduled > 0 && (
            <span className="stat-badge">
              <span className="dot scheduled" /> {scheduled} scheduled
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
        {view === "jobs" || view === "agentflow" ? (
          <button className="btn btn-primary" onClick={onNewJob}>
            + New Job
          </button>
        ) : view === "assistants" ? (
          <button className="btn btn-primary" onClick={onNewAssistant}>
            + New Assistant
          </button>
        ) : (
          <button className="btn btn-primary" onClick={onNewSchedule}>
            + New Schedule
          </button>
        )}
      </div>
    </header>
  );
}
