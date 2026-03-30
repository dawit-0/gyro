import React, { useState } from "react";
import { api, Project } from "../api";

interface Props {
  projects: Project[];
  selectedProject: string | null;
  onClose: () => void;
  onCreated: () => void;
}

const MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet" },
  { value: "claude-opus-4-20250514", label: "Claude Opus" },
  { value: "claude-haiku-3-5-20241022", label: "Claude Haiku" },
];

export default function JobForm({ projects, selectedProject, onClose, onCreated }: Props) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [model, setModel] = useState(MODELS[0].value);
  const [workDir, setWorkDir] = useState("");
  const [projectId, setProjectId] = useState(selectedProject || "");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !prompt.trim()) return;
    setSubmitting(true);
    try {
      await api.jobs.create({
        title: title.trim(),
        prompt: prompt.trim(),
        model,
        work_dir: workDir.trim(),
        project_id: projectId || undefined,
      });
      onCreated();
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>New Job</h2>
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
              placeholder="Detailed instructions for the agent..."
            />
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

          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !title.trim() || !prompt.trim()}
            >
              {submitting ? "Creating..." : "Create Job"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
