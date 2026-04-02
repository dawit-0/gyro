import React, { useEffect, useState } from "react";
import { Task, TaskRun, TaskRunOutput, api } from "../api";
import { socket } from "../socket";

interface Props {
  task: Task;
  tasks: Task[];
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onTrigger: (id: string) => void;
}

export default function TaskCard({ task, tasks, onCancel, onDelete, onTrigger }: Props) {
  const [latestRun, setLatestRun] = useState<TaskRun | null>(null);
  const [output, setOutput] = useState<TaskRunOutput[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    api.taskRuns.list(task.id).then((runs) => {
      if (runs.length > 0) {
        const latest = runs[0]; // already sorted by run_number DESC
        setLatestRun(latest);
        if (latest.status === "running" || latest.status === "success" || latest.status === "failed") {
          api.taskRuns.output(latest.id).then(setOutput);
        }
        if (latest.status === "running") {
          setExpanded(true);
        }
      } else {
        setLatestRun(null);
        setOutput([]);
      }
    });
  }, [task.id, task.updated_at]);

  useEffect(() => {
    function onOutput(data: {
      task_run_id: string;
      task_id: string;
      seq: number;
      type: string;
      content: string;
    }) {
      if (data.task_id === task.id) {
        setOutput((prev) => [
          ...prev,
          {
            id: data.seq,
            task_run_id: data.task_run_id,
            seq: data.seq,
            type: data.type,
            content: data.content,
            timestamp: new Date().toISOString(),
          },
        ]);
        setExpanded(true);
      }
    }

    socket.on("task_run:output", onOutput);
    return () => {
      socket.off("task_run:output", onOutput);
    };
  }, [task.id]);

  const runStatus = latestRun?.status;
  const duration = latestRun?.duration_ms
    ? `${(latestRun.duration_ms / 1000).toFixed(1)}s`
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

  const displayStatus = runStatus || "idle";

  return (
    <div className={`task-card status-${displayStatus}`}>
      <div
        className="task-card-header"
        onClick={() => setExpanded(!expanded)}
        style={{ cursor: "pointer" }}
      >
        <h3>
          {task.schedule && <span className="schedule-badge" title={`Schedule: ${task.schedule}`}>&#x23f0; </span>}
          {task.title}
        </h3>
        <span className={`status-pill ${displayStatus}`}>{displayStatus}</span>
      </div>

      <div className="task-card-meta">
        <span>{task.model.split("-").slice(0, 2).join("-")}</span>
        {duration && <span>{duration}</span>}
        {latestRun?.num_turns ? <span>{latestRun.num_turns} turns</span> : null}
        {latestRun && <span>Run #{latestRun.run_number}</span>}
        {task.permissions?.preset && (
          <span className={`permission-badge perm-${task.permissions.preset}`}>
            {task.permissions.preset === "read-only"
              ? "read-only"
              : task.permissions.preset === "standard"
              ? "standard"
              : task.permissions.preset === "full"
              ? "full access"
              : "custom"}
          </span>
        )}
        {task.schedule && (
          <span className="schedule-meta">{task.schedule}</span>
        )}
      </div>

      {expanded && (
        <>
          <div className="task-card-output">
            {outputText || (
              <span style={{ color: "var(--text-muted)" }}>
                {runStatus === "queued"
                  ? "Waiting in queue..."
                  : runStatus === "running"
                  ? "Task starting..."
                  : !runStatus
                  ? "No runs yet. Click trigger to start."
                  : "No output"}
              </span>
            )}
          </div>
          <div className="task-card-actions">
            {(runStatus === "running" || runStatus === "queued") && (
              <button
                className="btn btn-danger btn-sm"
                onClick={() => onCancel(task.id)}
              >
                Cancel
              </button>
            )}
            {(!runStatus || runStatus === "success" || runStatus === "failed" || runStatus === "cancelled") && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => onTrigger(task.id)}
              >
                Trigger
              </button>
            )}
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onDelete(task.id)}
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
}
