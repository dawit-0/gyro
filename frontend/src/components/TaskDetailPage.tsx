import React, { useCallback, useEffect, useState } from "react";
import { api, Task, TaskRun, TaskRunOutput } from "../api";

interface Props {
  taskId: string;
  onBack: () => void;
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onTrigger: (id: string) => void;
  onRetryTask: (id: string) => void;
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.round((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

function eventLabel(parsed: Record<string, unknown>): string {
  const evt = parsed.event as string;
  switch (evt) {
    case "subprocess_started":
      return `Process started (pid ${parsed.pid})`;
    case "subprocess_exited": {
      const code = parsed.exit_code as number;
      const dur = parsed.duration_ms as number | undefined;
      return `Exited code ${code}${dur ? ` (${formatDuration(dur)})` : ""}`;
    }
    case "cascade_triggered":
      return "Triggered downstream tasks";
    case "retry_scheduled":
      return `Retry #${parsed.attempt} scheduled in ${parsed.delay_seconds}s`;
    default:
      return evt || "event";
  }
}

function eventColorClass(parsed: Record<string, unknown>): string {
  const evt = parsed.event as string;
  switch (evt) {
    case "subprocess_started":
      return "accent";
    case "subprocess_exited":
      return (parsed.exit_code as number) === 0 ? "success" : "danger";
    case "cascade_triggered":
      return "accent";
    case "retry_scheduled":
      return "warning";
    default:
      return "accent";
  }
}

export default function TaskDetailPage({
  taskId,
  onBack,
  onCancel,
  onDelete,
  onTrigger,
  onRetryTask,
}: Props) {
  const [task, setTask] = useState<Task | null>(null);
  const [runs, setRuns] = useState<TaskRun[]>([]);
  const [selectedRunIdx, setSelectedRunIdx] = useState(0);
  const [output, setOutput] = useState<TaskRunOutput[]>([]);
  const [promptExpanded, setPromptExpanded] = useState(false);
  const [deps, setDeps] = useState<{ depends_on: string[] }>({ depends_on: [] });

  const loadTask = useCallback(async () => {
    const t = await api.tasks.get(taskId);
    setTask(t);
  }, [taskId]);

  const loadRuns = useCallback(async () => {
    const r = await api.taskRuns.list(taskId);
    setRuns(r);
    if (r.length > 0) setSelectedRunIdx(0);
  }, [taskId]);

  const loadDeps = useCallback(async () => {
    const d = await api.tasks.dependencies(taskId);
    setDeps(d);
  }, [taskId]);

  useEffect(() => {
    loadTask();
    loadRuns();
    loadDeps();
  }, [loadTask, loadRuns, loadDeps]);

  // Load output when selected run changes
  useEffect(() => {
    if (runs.length === 0) {
      setOutput([]);
      return;
    }
    let cancelled = false;
    async function loadOutput() {
      const run = runs[selectedRunIdx];
      if (!run) return;
      const out = await api.taskRuns.output(run.id);
      if (!cancelled) setOutput(out);
    }
    loadOutput();
    return () => { cancelled = true; };
  }, [runs, selectedRunIdx]);

  // Poll for updates
  useEffect(() => {
    const interval = setInterval(() => {
      loadTask();
      loadRuns();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadTask, loadRuns]);

  if (!task) {
    return (
      <div className="task-detail-page">
        <div className="task-detail-loading">Loading...</div>
      </div>
    );
  }

  const selectedRun = runs[selectedRunIdx] || null;
  const displayStatus = selectedRun?.status || task.latest_run?.status || "idle";
  const isRunning = displayStatus === "running" || displayStatus === "queued";
  const isFailed = displayStatus === "failed" || displayStatus === "cancelled";

  const permissions = task.permissions;
  const enabledPerms = Object.entries(permissions)
    .filter(([k, v]) => k !== "preset" && v === true)
    .map(([k]) => k.replace("_", " "));

  return (
    <div className="task-detail-page">
      {/* Header */}
      <div className="task-detail-header">
        <div className="task-detail-header-left">
          <button className="btn btn-sm btn-secondary" onClick={onBack}>
            &larr; Back
          </button>
          <h2 className="task-detail-title">{task.title}</h2>
          <span className={`status-pill ${displayStatus}`}>{displayStatus}</span>
        </div>
        <div className="task-detail-header-actions">
          {isRunning && (
            <button className="btn btn-sm btn-danger" onClick={() => onCancel(taskId)}>
              Cancel
            </button>
          )}
          {isFailed && (
            <button className="btn btn-sm btn-retry" onClick={() => onRetryTask(taskId)}>
              &#x21bb; Retry
            </button>
          )}
          {!isRunning && (
            <button className="btn btn-sm btn-primary" onClick={() => onTrigger(taskId)}>
              Trigger
            </button>
          )}
          <button className="btn btn-sm btn-secondary" onClick={() => { onDelete(taskId); onBack(); }}>
            Delete
          </button>
        </div>
      </div>

      {/* Meta row */}
      <div className="task-detail-meta">
        <span className="task-detail-meta-item">{task.model}</span>
        {task.schedule && (
          <span className="task-detail-meta-item">Schedule: {task.schedule}</span>
        )}
        <span className="task-detail-meta-item">Created: {formatTimestamp(task.created_at)}</span>
        {task.flow_id && (
          <span className="task-detail-meta-item">Flow: {task.flow_id.slice(0, 8)}</span>
        )}
      </div>

      {/* Body: two columns */}
      <div className="task-detail-body">
        {/* Left: Task Config */}
        <div className="task-detail-config">
          <div className="task-detail-section">
            <div className="task-detail-section-label">Prompt</div>
            <div
              className={`task-detail-prompt ${promptExpanded ? "expanded" : ""}`}
              onClick={() => setPromptExpanded(!promptExpanded)}
            >
              <pre>{task.prompt}</pre>
            </div>
            {task.prompt.length > 200 && (
              <button
                className="task-detail-prompt-toggle"
                onClick={() => setPromptExpanded(!promptExpanded)}
              >
                {promptExpanded ? "Show less" : "Show more"}
              </button>
            )}
          </div>

          {task.work_dir && (
            <div className="task-detail-section">
              <div className="task-detail-section-label">Working Directory</div>
              <code className="task-detail-code">{task.work_dir}</code>
            </div>
          )}

          <div className="task-detail-section">
            <div className="task-detail-section-label">Permissions ({permissions.preset})</div>
            <div className="task-detail-permissions">
              {enabledPerms.map((p) => (
                <span key={p} className="task-detail-perm-pill">{p}</span>
              ))}
              {enabledPerms.length === 0 && (
                <span className="task-detail-perm-none">None</span>
              )}
            </div>
          </div>

          {deps.depends_on.length > 0 && (
            <div className="task-detail-section">
              <div className="task-detail-section-label">Dependencies</div>
              <div className="task-detail-dep-list">
                {deps.depends_on.map((id) => (
                  <span key={id} className="task-detail-dep-chip">{id.slice(0, 8)}</span>
                ))}
              </div>
            </div>
          )}

          <div className="task-detail-section">
            <div className="task-detail-section-label">Retry Configuration</div>
            <div className="task-detail-kv">
              <span>Max retries:</span>
              <span>{task.latest_run?.attempt_number !== undefined ? `${task.latest_run.attempt_number}` : "0"}</span>
            </div>
            {task.schedule && (
              <>
                <div className="task-detail-kv">
                  <span>Next run:</span>
                  <span>{task.next_run_at ? formatTimestamp(task.next_run_at) : "N/A"}</span>
                </div>
                <div className="task-detail-kv">
                  <span>Last run:</span>
                  <span>{task.last_run_at ? formatTimestamp(task.last_run_at) : "Never"}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right: Run History */}
        <div className="task-detail-runs">
          {runs.length > 0 ? (
            <>
              {/* Run selector */}
              <div className="task-detail-section">
                <div className="task-detail-section-label">Run History ({runs.length} runs)</div>
                <div className="task-detail-run-selector">
                  {runs.map((run, idx) => (
                    <button
                      key={run.id}
                      className={`task-detail-run-pill ${idx === selectedRunIdx ? "active" : ""}`}
                      onClick={() => setSelectedRunIdx(idx)}
                    >
                      <span className={`run-pill-dot ${run.status}`} />
                      #{run.run_number}
                    </button>
                  ))}
                </div>
              </div>

              {/* Selected run details */}
              {selectedRun && (
                <>
                  <div className="task-detail-section">
                    <div className="task-detail-section-label">Run #{selectedRun.run_number} Details</div>
                    <div className="task-detail-run-meta">
                      <div className="task-detail-kv">
                        <span>Status:</span>
                        <span className={`status-pill ${selectedRun.status}`}>{selectedRun.status}</span>
                      </div>
                      <div className="task-detail-kv">
                        <span>Trigger:</span>
                        <span>{selectedRun.trigger}</span>
                      </div>
                      {selectedRun.duration_ms > 0 && (
                        <div className="task-detail-kv">
                          <span>Duration:</span>
                          <span>{formatDuration(selectedRun.duration_ms)}</span>
                        </div>
                      )}
                      {selectedRun.cost_usd > 0 && (
                        <div className="task-detail-kv">
                          <span>Cost:</span>
                          <span>${selectedRun.cost_usd.toFixed(4)}</span>
                        </div>
                      )}
                      {selectedRun.num_turns > 0 && (
                        <div className="task-detail-kv">
                          <span>Turns:</span>
                          <span>{selectedRun.num_turns}</span>
                        </div>
                      )}
                      {selectedRun.pid !== null && (
                        <div className="task-detail-kv">
                          <span>PID:</span>
                          <span>{selectedRun.pid}</span>
                        </div>
                      )}
                      {selectedRun.exit_code !== null && (
                        <div className="task-detail-kv">
                          <span>Exit code:</span>
                          <span>{selectedRun.exit_code}</span>
                        </div>
                      )}
                      {selectedRun.attempt_number > 1 && (
                        <div className="task-detail-kv">
                          <span>Attempt:</span>
                          <span>{selectedRun.attempt_number}</span>
                        </div>
                      )}
                      {selectedRun.started_at && (
                        <div className="task-detail-kv">
                          <span>Started:</span>
                          <span>{formatTimestamp(selectedRun.started_at)}</span>
                        </div>
                      )}
                      {selectedRun.finished_at && (
                        <div className="task-detail-kv">
                          <span>Finished:</span>
                          <span>{formatTimestamp(selectedRun.finished_at)}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Error */}
                  {selectedRun.error_message && (
                    <div className="task-detail-section">
                      <div className="task-detail-section-label">Error</div>
                      <pre className="task-detail-error-pre">{selectedRun.error_message}</pre>
                    </div>
                  )}

                  {/* Timeline */}
                  {output.length > 0 && (
                    <div className="task-detail-section task-detail-timeline-section">
                      <div className="task-detail-section-label">Timeline</div>
                      <div className="task-detail-timeline">
                        {output.map((o) => {
                          if (o.type === "event") {
                            try {
                              const parsed = JSON.parse(o.content) as Record<string, unknown>;
                              return (
                                <div className="timeline-event" key={o.seq}>
                                  <span className="timeline-event-time">
                                    {formatTimestamp(o.timestamp)}
                                  </span>
                                  <span className={`timeline-event-pill ${eventColorClass(parsed)}`}>
                                    {eventLabel(parsed)}
                                  </span>
                                </div>
                              );
                            } catch {
                              return null;
                            }
                          }
                          if (["assistant", "text", "result"].includes(o.type)) {
                            return (
                              <pre className="timeline-text" key={o.seq}>
                                {o.content}
                              </pre>
                            );
                          }
                          return null;
                        })}
                      </div>
                    </div>
                  )}
                </>
              )}
            </>
          ) : (
            <div className="task-detail-no-runs">
              No runs yet. Click "Trigger" to start a run.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
