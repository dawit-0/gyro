import React from "react";
import { Job } from "../api";

interface Props {
  jobs: Job[];
  onNewJob: () => void;
}

export default function Header({ jobs, onNewJob }: Props) {
  const running = jobs.filter((j) => j.status === "running").length;
  const queued = jobs.filter((j) => j.status === "queued").length;
  const done = jobs.filter((j) => j.status === "done").length;
  const failed = jobs.filter((j) => j.status === "failed").length;

  return (
    <header className="header">
      <div className="header-logo">
        <img src="/gyro_new.png" alt="gyro" className="header-logo-icon" />
        gyro
      </div>
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
      <div className="header-actions">
        <button className="btn btn-primary" onClick={onNewJob}>
          + New Job
        </button>
      </div>
    </header>
  );
}
