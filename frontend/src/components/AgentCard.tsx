import React, { useEffect, useState } from "react";
import { Job, Agent, AgentOutput, api } from "../api";
import { socket } from "../socket";

interface Props {
  job: Job;
  jobs: Job[];
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function AgentCard({ job, jobs, onCancel, onDelete }: Props) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [output, setOutput] = useState<AgentOutput[]>([]);
  const [expanded, setExpanded] = useState(job.status === "running");

  useEffect(() => {
    api.agents.list(job.id).then((agents) => {
      if (agents.length > 0) {
        setAgent(agents[0]);
        api.agents.output(agents[0].id).then(setOutput);
      }
    });
  }, [job.id, job.status]);

  useEffect(() => {
    function onOutput(data: {
      agent_id: string;
      job_id: string;
      seq: number;
      type: string;
      content: string;
    }) {
      if (data.job_id === job.id) {
        setOutput((prev) => [
          ...prev,
          {
            id: data.seq,
            agent_id: data.agent_id,
            seq: data.seq,
            type: data.type,
            content: data.content,
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    }

    socket.on("agent:output", onOutput);
    return () => {
      socket.off("agent:output", onOutput);
    };
  }, [job.id]);

  useEffect(() => {
    if (job.status === "running") setExpanded(true);
  }, [job.status]);

  const duration = agent?.duration_ms
    ? `${(agent.duration_ms / 1000).toFixed(1)}s`
    : null;

  const outputText = output
    .map((o) => {
      if (o.type === "text" || o.type === "assistant") return o.content;
      try {
        const parsed = JSON.parse(o.content);
        if (parsed.content) return parsed.content;
        if (parsed.result) return parsed.result;
      } catch {}
      return o.content;
    })
    .join("\n");

  return (
    <div className={`agent-card status-${job.status}`}>
      <div
        className="agent-card-header"
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: "pointer" }}
      >
        <h3>
          {job.schedule_id && <span className="recurring-badge" title="From recurring schedule">&#x21bb; </span>}
          {job.title}
        </h3>
        {job.status === "queued" && job.scheduled_for && new Date(job.scheduled_for) > new Date() ? (
          <span className="status-pill scheduled" title={new Date(job.scheduled_for).toLocaleString()}>
            &#x1f552; Scheduled
          </span>
        ) : job.status === "queued" && job.parent_job_id ? (
          <span className="status-pill queued" title="Waiting for parent job to complete">
            &#x23f3; Waiting
          </span>
        ) : (
          <span className={`status-pill ${job.status}`}>{job.status}</span>
        )}
      </div>

      <div className="agent-card-meta">
        <span>{job.model.split("-").slice(0, 2).join("-")}</span>
        {duration && <span>{duration}</span>}
        {agent?.num_turns ? <span>{agent.num_turns} turns</span> : null}
        {job.permissions?.preset && (
          <span className={`permission-badge perm-${job.permissions.preset}`}>
            {job.permissions.preset === "read-only"
              ? "read-only"
              : job.permissions.preset === "standard"
              ? "standard"
              : job.permissions.preset === "full"
              ? "full access"
              : "custom"}
          </span>
        )}
        {job.parent_job_id && (() => {
          const parent = jobs.find((j) => j.id === job.parent_job_id);
          return (
            <span className="dependency-badge" title={parent ? `Depends on: ${parent.title}` : "Depends on parent job"}>
              &#x21b3; {parent ? parent.title : "parent"}
            </span>
          );
        })()}
      </div>

      {expanded && (
        <>
          <div className="agent-card-output">
            {outputText || (
              <span style={{ color: "var(--text-muted)" }}>
                {job.status === "queued" && job.scheduled_for && new Date(job.scheduled_for) > new Date()
                  ? `Scheduled for ${new Date(job.scheduled_for).toLocaleString()}`
                  : job.status === "queued" && job.parent_job_id
                  ? "Waiting on parent job..."
                  : job.status === "queued"
                  ? "Waiting in queue..."
                  : job.status === "running"
                  ? "Agent starting..."
                  : "No output"}
              </span>
            )}
          </div>
          <div className="agent-card-actions">
            {(job.status === "running" || job.status === "queued") && (
              <button
                className="btn btn-danger btn-sm"
                onClick={() => onCancel(job.id)}
              >
                Cancel
              </button>
            )}
            {(job.status === "done" ||
              job.status === "failed" ||
              job.status === "cancelled") && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => onDelete(job.id)}
              >
                Remove
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
