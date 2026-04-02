import React, { useState } from "react";
import { Flow, Task, api } from "../api";

interface Props {
  flows: Flow[];
  selectedFlow: string | null;
  onSelectFlow: (id: string | null) => void;
  onFlowsChange: () => void;
  tasks: Task[];
}

export default function Sidebar({
  flows,
  selectedFlow,
  onSelectFlow,
  onFlowsChange,
  tasks,
}: Props) {
  const [newName, setNewName] = useState("");
  const [showForm, setShowForm] = useState(false);

  async function handleCreate() {
    if (!newName.trim()) return;
    await api.flows.create({ name: newName.trim() });
    setNewName("");
    setShowForm(false);
    onFlowsChange();
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <h3>Flows</h3>
        <div
          className={`project-item ${selectedFlow === null ? "active" : ""}`}
          onClick={() => onSelectFlow(null)}
        >
          All Tasks
        </div>
        {flows.map((f) => (
          <div
            key={f.id}
            className={`project-item ${selectedFlow === f.id ? "active" : ""}`}
            onClick={() => onSelectFlow(f.id)}
          >
            <span>{f.name}</span>
            {f.schedule && <span className="flow-schedule-badge" title={f.schedule}>&#x23f0;</span>}
          </div>
        ))}
        {showForm ? (
          <div style={{ marginTop: 8 }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Flow name"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              style={{
                width: "100%",
                padding: "6px 10px",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius)",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
                outline: "none",
              }}
              autoFocus
            />
          </div>
        ) : (
          <div
            className="project-item"
            style={{ color: "var(--accent)", marginTop: 4 }}
            onClick={() => setShowForm(true)}
          >
            + New Flow
          </div>
        )}
      </div>

      <div className="sidebar-section">
        <h3>Summary</h3>
        <div className="sidebar-summary">
          <div className="summary-item">
            <span className="summary-count">{tasks.length}</span>
            <span className="summary-label">Tasks</span>
          </div>
          <div className="summary-item">
            <span className="summary-count">{tasks.filter((t) => t.schedule).length}</span>
            <span className="summary-label">Scheduled</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
