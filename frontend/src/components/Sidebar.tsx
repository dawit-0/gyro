import React, { useState } from "react";
import { Project, Job, api } from "../api";

interface Props {
  projects: Project[];
  selectedProject: string | null;
  onSelectProject: (id: string | null) => void;
  onProjectsChange: () => void;
  jobs: Job[];
}

export default function Sidebar({
  projects,
  selectedProject,
  onSelectProject,
  onProjectsChange,
  jobs,
}: Props) {
  const [newName, setNewName] = useState("");
  const [showForm, setShowForm] = useState(false);

  const queuedJobs = jobs.filter((j) => j.status === "queued");

  async function handleCreate() {
    if (!newName.trim()) return;
    await api.projects.create({ name: newName.trim() });
    setNewName("");
    setShowForm(false);
    onProjectsChange();
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <h3>Projects</h3>
        <div
          className={`project-item ${selectedProject === null ? "active" : ""}`}
          onClick={() => onSelectProject(null)}
        >
          All Jobs
        </div>
        {projects.map((p) => (
          <div
            key={p.id}
            className={`project-item ${selectedProject === p.id ? "active" : ""}`}
            onClick={() => onSelectProject(p.id)}
          >
            {p.name}
          </div>
        ))}
        {showForm ? (
          <div style={{ marginTop: 8 }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Project name"
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
            + New Project
          </div>
        )}
      </div>

      {queuedJobs.length > 0 && (
        <div className="sidebar-section">
          <h3>Queue ({queuedJobs.length})</h3>
          {queuedJobs.map((j) => (
            <div key={j.id} className="queue-item">
              <div className="queue-title">{j.title}</div>
              <div className="queue-meta">{j.model.split("-").slice(0, 2).join("-")}</div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
