import React, { useState } from "react";
import { api, Job, Project, Permissions, PERMISSION_PRESETS } from "../api";
import { JobPrefill } from "../App";

interface Props {
  projects: Project[];
  jobs: Job[];
  selectedProject: string | null;
  onClose: () => void;
  onCreated: () => void;
  prefill?: Partial<JobPrefill> | null;
}

const MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet" },
  { value: "claude-opus-4-20250514", label: "Claude Opus" },
  { value: "claude-haiku-3-5-20241022", label: "Claude Haiku" },
];

type ScheduleMode = "now" | "later" | "recurring";

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

export default function JobForm({ projects, jobs, selectedProject, onClose, onCreated, prefill }: Props) {
  const [title, setTitle] = useState(prefill?.title || "");
  const [prompt, setPrompt] = useState(prefill?.prompt || "");
  const [model, setModel] = useState(prefill?.model || MODELS[0].value);
  const [workDir, setWorkDir] = useState(prefill?.workDir || "");
  const [projectId, setProjectId] = useState(prefill?.projectId || selectedProject || "");
  const [permissions, setPermissions] = useState<Permissions>(
    prefill?.permissions?.preset ? prefill.permissions : PERMISSION_PRESETS["standard"]
  );
  const [showPermDetails, setShowPermDetails] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Dependency state (multi-select)
  const [dependsOn, setDependsOn] = useState<string[]>(
    prefill?.parentJobId ? [prefill.parentJobId] : []
  );

  // Scheduling state
  const [scheduleMode, setScheduleMode] = useState<ScheduleMode>("now");
  const [scheduledFor, setScheduledFor] = useState("");
  const [cronExpression, setCronExpression] = useState(CRON_PRESETS[1].value);
  const [scheduleName, setScheduleName] = useState("");

  const isSpawn = !!prefill?.assistantId;
  const isRecurring = scheduleMode === "recurring";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    if (!isRecurring && !title.trim()) return;
    if (isRecurring && !scheduleName.trim()) return;
    setSubmitting(true);
    try {
      if (isRecurring) {
        await api.schedules.create({
          name: scheduleName.trim(),
          cron_expression: cronExpression,
          title_template: title.trim() || scheduleName.trim() + " #{n}",
          prompt: prompt.trim(),
          model,
          work_dir: workDir.trim(),
          project_id: projectId || undefined,
          permissions,
          assistant_id: prefill?.assistantId || undefined,
        });
      } else {
        const scheduled_for =
          scheduleMode === "later" && scheduledFor
            ? new Date(scheduledFor).toISOString()
            : undefined;

        if (isSpawn && prefill?.assistantId) {
          await api.assistants.spawn(prefill.assistantId, {
            title: title.trim(),
            prompt: prompt.trim(),
            model,
            work_dir: workDir.trim(),
            project_id: projectId || undefined,
            permissions,
            scheduled_for,
            depends_on: dependsOn.length > 0 ? dependsOn : undefined,
          });
        } else {
          await api.jobs.create({
            title: title.trim(),
            prompt: prompt.trim(),
            model,
            work_dir: workDir.trim(),
            project_id: projectId || undefined,
            permissions,
            scheduled_for,
            depends_on: dependsOn.length > 0 ? dependsOn : undefined,
          });
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
    if (isRecurring) return "Create Schedule";
    if (isSpawn) return "Spawn Job";
    if (scheduleMode === "later") return "Schedule Job";
    return "Create Job";
  }

  const isValid =
    prompt.trim() &&
    (isRecurring ? scheduleName.trim() && cronExpression : title.trim()) &&
    (scheduleMode !== "later" || scheduledFor);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isRecurring ? "New Recurring Schedule" : isSpawn ? "Spawn Job from Assistant" : "New Job"}</h2>
        <form onSubmit={handleSubmit}>
          {isRecurring && (
            <div className="form-group">
              <label>Schedule Name</label>
              <input
                value={scheduleName}
                onChange={(e) => setScheduleName(e.target.value)}
                placeholder="e.g. Daily code review"
                autoFocus
              />
            </div>
          )}

          <div className="form-group">
            <label>{isRecurring ? "Job Title Template" : "Title"}</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={isRecurring ? "e.g. Code review {date} #{n}" : "Brief description of the task"}
              autoFocus={!isRecurring}
            />
            {isRecurring && (
              <p className="field-hint">Use {"{date}"} for date and {"{n}"} for run number</p>
            )}
          </div>

          <div className="form-group">
            <label>Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isSpawn ? "Describe the specific task for this job..." : "Detailed instructions for the agent..."}
            />
          </div>

          <div className="form-group">
            <label>Scheduling</label>
            <div className="schedule-modes">
              <button
                type="button"
                className={`btn btn-sm${scheduleMode === "now" ? " active" : ""}`}
                onClick={() => setScheduleMode("now")}
              >
                Run Now
              </button>
              <button
                type="button"
                className={`btn btn-sm${scheduleMode === "later" ? " active" : ""}`}
                onClick={() => setScheduleMode("later")}
              >
                Run Later
              </button>
              <button
                type="button"
                className={`btn btn-sm${scheduleMode === "recurring" ? " active" : ""}`}
                onClick={() => setScheduleMode("recurring")}
              >
                Recurring
              </button>
            </div>

            {scheduleMode === "later" && (
              <div className="schedule-config">
                <input
                  type="datetime-local"
                  value={scheduledFor}
                  onChange={(e) => setScheduledFor(e.target.value)}
                  min={new Date().toISOString().slice(0, 16)}
                />
              </div>
            )}

            {scheduleMode === "recurring" && (
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
            <label>Project (optional)</label>
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
              <option value="">None</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!isRecurring && jobs.length > 0 && (
            <div className="form-group">
              <label>Depends On (optional)</label>
              <div className="depends-on-list">
                {jobs.map((j) => (
                  <label key={j.id} className="permission-toggle">
                    <input
                      type="checkbox"
                      checked={dependsOn.includes(j.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setDependsOn([...dependsOn, j.id]);
                        } else {
                          setDependsOn(dependsOn.filter((id) => id !== j.id));
                        }
                      }}
                    />
                    <span>{j.title}</span>
                    <span className={`flow-node-status ${j.status}`}>{j.status}</span>
                  </label>
                ))}
              </div>
              {dependsOn.length > 0 && (
                <p className="field-hint">This job will run after all selected jobs succeed.</p>
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
