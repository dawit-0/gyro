import React, { useState } from "react";
import { Flow, Task, Assistant, api } from "../api";

interface Props {
  flows: Flow[];
  selectedFlow: string | null;
  onSelectFlow: (id: string | null) => void;
  onFlowsChange: () => void;
  tasks: Task[];
  view: "tasks" | "assistants" | "taskflow";
  assistants: Assistant[];
  onNewTask: () => void;
  onNewAssistant: () => void;
  onSpawnAssistant: (assistant: Assistant) => void;
  onEditAssistant: (assistant: Assistant) => void;
  onTriggerFlow: (id: string) => void;
  onRetryFlow: (id: string) => void;
  onResumeFlow: (id: string) => void;
}

export default function Sidebar({
  flows,
  selectedFlow,
  onSelectFlow,
  onFlowsChange,
  tasks,
  view,
  assistants,
  onNewTask,
  onNewAssistant,
  onSpawnAssistant,
  onEditAssistant,
  onTriggerFlow,
  onRetryFlow,
  onResumeFlow,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const [newName, setNewName] = useState("");
  const [showForm, setShowForm] = useState(false);

  async function handleCreate() {
    if (!newName.trim()) return;
    await api.flows.create({ name: newName.trim() });
    setNewName("");
    setShowForm(false);
    onFlowsChange();
  }

  const runningTasks = tasks.filter(
    (t) => t.latest_run?.status === "running"
  );
  const failedTasks = tasks.filter(
    (t) => t.latest_run?.status === "failed"
  );
  const scheduledTasks = tasks.filter((t) => t.schedule);
  const queuedTasks = tasks.filter(
    (t) => t.latest_run?.status === "queued"
  );

  const selectedFlowData = flows.find((f) => f.id === selectedFlow);

  return (
    <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}>
      <button
        className="sidebar-toggle"
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className={`sidebar-toggle-icon ${collapsed ? "rotated" : ""}`}
        >
          <path
            d="M10 12L6 8L10 4"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>

      {!collapsed && (
        <div className="sidebar-inner">
          {/* ── Tasks Tab ── */}
          {view === "tasks" && (
            <>
              <div className="sidebar-section">
                <h3>Flows</h3>
                <div
                  className={`project-item ${selectedFlow === null ? "active" : ""}`}
                  onClick={() => onSelectFlow(null)}
                >
                  <span>All Tasks</span>
                  <span className="sidebar-count">{tasks.length}</span>
                </div>
                {flows.map((f) => {
                  const count = tasks.filter((t) => t.flow_id === f.id).length;
                  return (
                    <div
                      key={f.id}
                      className={`project-item ${selectedFlow === f.id ? "active" : ""}`}
                      onClick={() => onSelectFlow(f.id)}
                    >
                      <span>{f.name}</span>
                      <span className="sidebar-item-right">
                        {f.schedule && (
                          <span className="flow-schedule-badge" title={f.schedule}>
                            &#x23f0;
                          </span>
                        )}
                        <span className="sidebar-count">{count}</span>
                      </span>
                    </div>
                  );
                })}
                {showForm ? (
                  <div style={{ marginTop: 8 }}>
                    <input
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      placeholder="Flow name"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleCreate();
                        if (e.key === "Escape") {
                          setShowForm(false);
                          setNewName("");
                        }
                      }}
                      className="sidebar-inline-input"
                      autoFocus
                    />
                  </div>
                ) : (
                  <div
                    className="project-item sidebar-add-item"
                    onClick={() => setShowForm(true)}
                  >
                    + New Flow
                  </div>
                )}
              </div>

              <div className="sidebar-section">
                <h3>Quick Actions</h3>
                <button className="sidebar-action-btn" onClick={onNewTask}>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  New Task
                </button>
              </div>

              <div className="sidebar-section">
                <h3>Overview</h3>
                <div className="sidebar-stats">
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value">{tasks.length}</span>
                    <span className="sidebar-stat-label">Total</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-running">
                      {runningTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Running</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-failed">
                      {failedTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Failed</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-scheduled">
                      {scheduledTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Scheduled</span>
                  </div>
                </div>
              </div>

              {runningTasks.length > 0 && (
                <div className="sidebar-section">
                  <h3>Running Now</h3>
                  {runningTasks.slice(0, 5).map((t) => (
                    <div key={t.id} className="sidebar-activity-item">
                      <span className="sidebar-activity-dot running" />
                      <span className="sidebar-activity-text">{t.title}</span>
                    </div>
                  ))}
                  {runningTasks.length > 5 && (
                    <span className="sidebar-more-text">
                      +{runningTasks.length - 5} more
                    </span>
                  )}
                </div>
              )}
            </>
          )}

          {/* ── Assistants Tab ── */}
          {view === "assistants" && (
            <>
              <div className="sidebar-section">
                <h3>Quick Actions</h3>
                <button className="sidebar-action-btn" onClick={onNewAssistant}>
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                    <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                  New Assistant
                </button>
              </div>

              <div className="sidebar-section">
                <h3>Assistants ({assistants.length})</h3>
                {assistants.length === 0 ? (
                  <div className="sidebar-empty-hint">
                    No assistants yet. Create one to get started.
                  </div>
                ) : (
                  assistants.map((a) => (
                    <div key={a.id} className="sidebar-assistant-item">
                      <div className="sidebar-assistant-name">{a.name}</div>
                      {a.description && (
                        <div className="sidebar-assistant-desc">
                          {a.description}
                        </div>
                      )}
                      <div className="sidebar-assistant-actions">
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={() => onSpawnAssistant(a)}
                        >
                          Spawn
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => onEditAssistant(a)}
                        >
                          Edit
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>

              <div className="sidebar-section">
                <h3>Overview</h3>
                <div className="sidebar-stats">
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value">{assistants.length}</span>
                    <span className="sidebar-stat-label">Assistants</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value">{tasks.length}</span>
                    <span className="sidebar-stat-label">Tasks</span>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ── TaskFlow Tab ── */}
          {view === "taskflow" && (
            <>
              <div className="sidebar-section">
                <h3>Flows</h3>
                <div
                  className={`project-item ${selectedFlow === null ? "active" : ""}`}
                  onClick={() => onSelectFlow(null)}
                >
                  <span>All Flows</span>
                </div>
                {flows.map((f) => (
                  <div
                    key={f.id}
                    className={`project-item ${selectedFlow === f.id ? "active" : ""}`}
                    onClick={() => onSelectFlow(f.id)}
                  >
                    <span>{f.name}</span>
                    {f.schedule && (
                      <span className="flow-schedule-badge" title={f.schedule}>
                        &#x23f0;
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {selectedFlow && selectedFlowData && (
                <div className="sidebar-section">
                  <h3>Flow Actions</h3>
                  <button
                    className="sidebar-action-btn"
                    onClick={() => onTriggerFlow(selectedFlow)}
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path d="M4 2l10 6-10 6V2z" fill="currentColor" />
                    </svg>
                    Trigger Flow
                  </button>
                  <button
                    className="sidebar-action-btn sidebar-action-warning"
                    onClick={() => onRetryFlow(selectedFlow)}
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path
                        d="M2 8a6 6 0 0111.5-2.5M14 8a6 6 0 01-11.5 2.5"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                      <path d="M14 2v4h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M2 14v-4h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    Retry Failed
                  </button>
                  <button
                    className="sidebar-action-btn sidebar-action-accent"
                    onClick={() => onResumeFlow(selectedFlow)}
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path d="M3 2l5 6-5 6V2z" fill="currentColor" />
                      <path d="M9 2l5 6-5 6V2z" fill="currentColor" />
                    </svg>
                    Resume Flow
                  </button>
                  <button className="sidebar-action-btn" onClick={onNewTask}>
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                      <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    Add Task to Flow
                  </button>
                </div>
              )}

              <div className="sidebar-section">
                <h3>Flow Stats</h3>
                <div className="sidebar-stats">
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value">{flows.length}</span>
                    <span className="sidebar-stat-label">Flows</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-running">
                      {runningTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Running</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-queued">
                      {queuedTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Queued</span>
                  </div>
                  <div className="sidebar-stat">
                    <span className="sidebar-stat-value sidebar-stat-failed">
                      {failedTasks.length}
                    </span>
                    <span className="sidebar-stat-label">Failed</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
