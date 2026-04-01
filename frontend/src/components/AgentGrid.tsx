import React from "react";
import { Job } from "../api";
import AgentCard from "./AgentCard";

interface Props {
  jobs: Job[];
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onNewJob: () => void;
}

export default function AgentGrid({ jobs, onCancel, onDelete, onNewJob }: Props) {
  const activeJobs = jobs.filter(
    (j) => j.status !== "queued"
  );

  if (activeJobs.length === 0) {
    return (
      <div className="empty-state">
        <h2>No agents running</h2>
        <p>Create a job to get started. Jobs are dispatched to Claude agents automatically.</p>
        <button className="btn btn-primary" onClick={onNewJob}>
          + New Job
        </button>
      </div>
    );
  }

  // Sort: running first, then by created_at desc
  const sorted = [...activeJobs].sort((a, b) => {
    const order: Record<string, number> = { running: 0, assigned: 1, failed: 2, done: 3, cancelled: 4 };
    const diff = (order[a.status] ?? 5) - (order[b.status] ?? 5);
    if (diff !== 0) return diff;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div className="agent-grid">
      {sorted.map((job) => (
        <AgentCard
          key={job.id}
          job={job}
          jobs={jobs}
          onCancel={onCancel}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
