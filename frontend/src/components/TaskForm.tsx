import React, { useState } from "react";
import { api, Task, Flow, Permissions, PERMISSION_PRESETS } from "../api";
import { TaskPrefill } from "../App";

interface Props {
  flows: Flow[];
  tasks: Task[];
  selectedFlow: string | null;
  onClose: () => void;
  onCreated: () => void;
  prefill?: Partial<TaskPrefill> | null;
}

const MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet" },
  { value: "claude-opus-4-20250514", label: "Claude Opus" },
  { value: "claude-haiku-3-5-20241022", label: "Claude Haiku" },
];

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Daily at 9am", value: "0 9 * * *" },
  { label: "Weekdays at 9am", value: "0 9 * * 1-5" },
  { label: "Weekly (Mon)", value: "0 9 * * 1" },
  { label: "Monthly (1st)", value: "0 9 1 * *" },
];

function describeCron(expr: string): string {
  const match = CRON_PRESETS.find((p) => p.value === expr);
  if (match) return match.label;
  return expr;
}

export default function TaskForm({ flows, tasks, selectedFlow, onClose, onCreated, prefill }: Props) {
  const [title, setTitle] = useState(prefill?.title || "");
  const [prompt, setPrompt] = useState(prefill?.prompt || "");
  const [model, setModel] = useState(prefill?.model || MODELS[0].value);
  const [workDir, setWorkDir] = useState(prefill?.workDir || "");
  const [flowId, setFlowId] = useState(prefill?.flowId || selectedFlow || "");
  const [permissions, setPermissions] = useState<Permissions>(
    prefill?.permissions?.preset ? prefill.permissions : PERMISSION_PRESETS["standard"]
  );
  const [showPermDetails, setShowPermDetails] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Dependency state (multi-select)
  const [dependsOn, setDependsOn] = useState<string[]>([]);

  // Schedule state
  const [hasSchedule, setHasSchedule] = useState(false);
  const [cronExpression, setCronExpression] = useState(CRON_PRESETS[1].value);

  // Retry config
  const [maxRetries, setMaxRetries] = useState(0);
  const [retryDelay, setRetryDelay] = useState(10);

  // Whether to trigger immediately
  const [triggerNow, setTriggerNow] = useState(true);

  const isSpawn = !!prefill?.assistantId;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim() || !title.trim()) return;
    setSubmitting(true);
    try {
      if (isSpawn && prefill?.assistantId) {
        await api.assistants.spawn(prefill.assistantId, {
          title: title.trim(),
          prompt: prompt.trim(),
          model,
          work_dir: workDir.trim(),
          flow_id: flowId || undefined,
          permissions,
          depends_on: dependsOn.length > 0 ? dependsOn : undefined,
          trigger: triggerNow,
        });
      } else {
        const task = await api.tasks.create({
          title: title.trim(),
          prompt: prompt.trim(),
          model,
          work_dir: workDir.trim(),
          flow_id: flowId || undefined,
          permissions,
          schedule: hasSchedule ? cronExpression : undefined,
          depends_on: dependsOn.length > 0 ? dependsOn : undefined,
          max_retries: maxRetries > 0 ? maxRetries : undefined,
          retry_delay_seconds: maxRetries > 0 ? retryDelay : undefined,
        } as Parameters<typeof api.tasks.create>[0]);

        // Trigger immediately if requested and no schedule
        if (triggerNow && !hasSchedule) {
          await api.tasks.trigger(task.id);
        }
      }
      onCreated();
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  function getSubmitLabel() {
    if (submitting) return "Creating...";
    if (isSpawn) return triggerNow ? "Spawn & Run" : "Spawn Task";
    if (hasSchedule) return "Create Scheduled Task";
    return triggerNow ? "Create & Run" : "Create Task";
  }

  const isValid = prompt.trim() && title.trim();

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isSpawn ? "Spawn Task from Assistant" : "New Task"}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Brief description of the task"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isSpawn ? "Describe the specific task..." : "Detailed instructions for the agent..."}
            />
          </div>

          <div className="form-group">
            <label>Schedule (optional)</label>
            <div className="schedule-toggle">
              <label className="permission-toggle">
                <input
                  type="checkbox"
                  checked={hasSchedule}
                  onChange={(e) => setHasSchedule(e.target.checked)}
                />
                <span>Run on a recurring schedule</span>
              </label>
            </div>

            {hasSchedule && (
              <div className="schedule-config">
                <div className="cron-presets">
                  {CRON_PRESETS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      className={`btn btn-sm${cronExpression === p.value ? " active" : ""}`}
                      onClick={() => setCronExpression(p.value)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                <input
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  placeholder="* * * * * (min hour dom mon dow)"
                  className="cron-input"
                />
                <p className="field-hint">Schedule: {describeCron(cronExpression)}</p>
              </div>
            )}
          </div>

          <div className="form-group">
            <label>Auto-Retry on Failure (optional)</label>
            <div className="retry-config">
              <div className="retry-config-row">
                <label className="retry-config-label">Max retries</label>
                <select
                  value={maxRetries}
                  onChange={(e) => setMaxRetries(Number(e.target.value))}
                  className="retry-select"
                >
                  <option value={0}>None</option>
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                  <option value={5}>5</option>
                </select>
              </div>
              {maxRetries > 0 && (
                <div className="retry-config-row">
                  <label className="retry-config-label">Delay between retries</label>
                  <select
                    value={retryDelay}
                    onChange={(e) => setRetryDelay(Number(e.target.value))}
                    className="retry-select"
                  >
                    <option value={5}>5 seconds</option>
                    <option value={10}>10 seconds</option>
                    <option value={30}>30 seconds</option>
                    <option value={60}>1 minute</option>
                    <option value={300}>5 minutes</option>
                  </select>
                </div>
              )}
            </div>
            {maxRetries > 0 && (
              <p className="field-hint">
                If this task fails, it will automatically retry up to {maxRetries} time{maxRetries > 1 ? "s" : ""} with a {retryDelay}s delay.
              </p>
            )}
          </div>

          {!hasSchedule && (
            <div className="form-group">
              <label className="permission-toggle">
                <input
                  type="checkbox"
                  checked={triggerNow}
                  onChange={(e) => setTriggerNow(e.target.checked)}
                />
                <span>Trigger immediately after creation</span>
              </label>
            </div>
          )}

          <div className="form-group">
            <label>Model</label>
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Working Directory (optional)</label>
            <input
              value={workDir}
              onChange={(e) => setWorkDir(e.target.value)}
              placeholder="/path/to/project"
            />
          </div>

          <div className="form-group">
            <label>Flow (optional)</label>
            <select value={flowId} onChange={(e) => setFlowId(e.target.value)}>
              <option value="">None (standalone task)</option>
              {flows.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          {tasks.length > 0 && (
            <div className="form-group">
              <label>Depends On (optional)</label>
              <div className="depends-on-list">
                {tasks.map((t) => (
                  <label key={t.id} className="permission-toggle">
                    <input
                      type="checkbox"
                      checked={dependsOn.includes(t.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setDependsOn([...dependsOn, t.id]);
                        } else {
                          setDependsOn(dependsOn.filter((id) => id !== t.id));
                        }
                      }}
                    />
                    <span>{t.title}</span>
                  </label>
                ))}
              </div>
              {dependsOn.length > 0 && (
                <p className="field-hint">This task will wait for all selected tasks to succeed before running.</p>
              )}
            </div>
          )}

          <div className="form-group">
            <label>Permissions</label>
            <div className="permission-presets">
              {Object.entries(PERMISSION_PRESETS).map(([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  className={`btn btn-sm permission-preset-btn${
                    permissions.preset === key ? " active" : ""
                  }`}
                  onClick={() => setPermissions(preset)}
                >
                  {key === "read-only" ? "Read Only" : key === "standard" ? "Standard" : "Full Access"}
                </button>
              ))}
            </div>
            <p className="permission-description">
              {permissions.preset === "read-only" &&
                "Agent can only read files. No writes, no shell commands."}
              {permissions.preset === "standard" &&
                "Agent can read/write files and run shell commands."}
              {permissions.preset === "full" &&
                "Agent has full access including web search and MCP tools."}
            </p>
            <button
              type="button"
              className="btn-link"
              onClick={() => setShowPermDetails(!showPermDetails)}
            >
              {showPermDetails ? "Hide details" : "Show details"}
            </button>
            {showPermDetails && (
              <div className="permission-details">
                {(
                  [
                    ["file_read", "File Read"],
                    ["file_write", "File Write"],
                    ["bash", "Shell Commands"],
                    ["web_search", "Web Search"],
                    ["mcp", "MCP Tools"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="permission-toggle">
                    <input
                      type="checkbox"
                      checked={permissions[key]}
                      onChange={(e) =>
                        setPermissions({
                          ...permissions,
                          preset: "custom",
                          [key]: e.target.checked,
                        })
                      }
                    />
                    {label}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !isValid}
            >
              {getSubmitLabel()}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
