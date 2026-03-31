import React, { useState } from "react";
import { api, Project, Assistant, ContextItem, Permissions, PERMISSION_PRESETS } from "../api";

interface Props {
  projects: Project[];
  assistant: Assistant | null;
  onClose: () => void;
  onSaved: () => void;
}

const MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet" },
  { value: "claude-opus-4-20250514", label: "Claude Opus" },
  { value: "claude-haiku-3-5-20241022", label: "Claude Haiku" },
];

export default function AssistantForm({ projects, assistant, onClose, onSaved }: Props) {
  const [name, setName] = useState(assistant?.name || "");
  const [description, setDescription] = useState(assistant?.description || "");
  const [instructions, setInstructions] = useState(assistant?.instructions || "");
  const [context, setContext] = useState<ContextItem[]>(assistant?.context || []);
  const [defaultModel, setDefaultModel] = useState(assistant?.default_model || MODELS[0].value);
  const [permissions, setPermissions] = useState<Permissions>(
    assistant?.default_permissions?.preset
      ? assistant.default_permissions
      : PERMISSION_PRESETS["standard"]
  );
  const [showPermDetails, setShowPermDetails] = useState(false);
  const [defaultWorkDir, setDefaultWorkDir] = useState(assistant?.default_work_dir || "");
  const [defaultProjectId, setDefaultProjectId] = useState(assistant?.default_project_id || "");
  const [submitting, setSubmitting] = useState(false);

  function addContextItem(type: "file" | "url" | "text") {
    const item: ContextItem = { type };
    if (type === "file") item.path = "";
    else if (type === "url") item.url = "";
    else item.content = "";
    setContext([...context, item]);
  }

  function updateContextItem(index: number, update: Partial<ContextItem>) {
    setContext(context.map((item, i) => (i === index ? { ...item, ...update } : item)));
  }

  function removeContextItem(index: number) {
    setContext(context.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const data = {
        name: name.trim(),
        description: description.trim(),
        instructions: instructions.trim(),
        context,
        default_model: defaultModel,
        default_permissions: permissions,
        default_work_dir: defaultWorkDir.trim(),
        default_project_id: defaultProjectId || undefined,
      };
      if (assistant) {
        await api.assistants.update(assistant.id, data);
      } else {
        await api.assistants.create(data);
      }
      onSaved();
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <h2>{assistant ? "Edit Assistant" : "New Assistant"}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Code Reviewer, API Docs Writer"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Description</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of what this assistant does"
            />
          </div>

          <div className="form-group">
            <label>Instructions</label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Persona and instructions for the agent. e.g. 'You are a senior code reviewer. Focus on correctness, performance, and security...'"
              className="textarea-tall"
            />
          </div>

          <div className="form-group">
            <label>Context</label>
            <div className="context-list">
              {context.map((item, i) => (
                <div key={i} className="context-item">
                  <span className="context-type-badge">{item.type}</span>
                  {item.type === "file" && (
                    <input
                      value={item.path || ""}
                      onChange={(e) => updateContextItem(i, { path: e.target.value })}
                      placeholder="/path/to/document.md"
                    />
                  )}
                  {item.type === "url" && (
                    <input
                      value={item.url || ""}
                      onChange={(e) => updateContextItem(i, { url: e.target.value })}
                      placeholder="https://docs.example.com/api"
                    />
                  )}
                  {item.type === "text" && (
                    <textarea
                      value={item.content || ""}
                      onChange={(e) => updateContextItem(i, { content: e.target.value })}
                      placeholder="Reference text or notes..."
                      className="textarea-short"
                    />
                  )}
                  <button
                    type="button"
                    className="btn-icon btn-danger-icon"
                    onClick={() => removeContextItem(i)}
                    title="Remove"
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
            <div className="context-add-buttons">
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => addContextItem("file")}>
                + File
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => addContextItem("url")}>
                + URL
              </button>
              <button type="button" className="btn btn-sm btn-secondary" onClick={() => addContextItem("text")}>
                + Text
              </button>
            </div>
          </div>

          <div className="form-group">
            <label>Default Model</label>
            <select value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)}>
              {MODELS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Default Working Directory (optional)</label>
            <input
              value={defaultWorkDir}
              onChange={(e) => setDefaultWorkDir(e.target.value)}
              placeholder="/path/to/project"
            />
          </div>

          <div className="form-group">
            <label>Default Project (optional)</label>
            <select value={defaultProjectId} onChange={(e) => setDefaultProjectId(e.target.value)}>
              <option value="">None</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Default Permissions</label>
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
              disabled={submitting || !name.trim()}
            >
              {submitting ? "Saving..." : assistant ? "Save Changes" : "Create Assistant"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
