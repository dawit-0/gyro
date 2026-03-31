import React from "react";
import { Assistant } from "../api";

interface Props {
  assistant: Assistant;
  onSpawn: (assistant: Assistant) => void;
  onEdit: (assistant: Assistant) => void;
  onDelete: (id: string) => void;
}

function getModelLabel(model: string): string {
  if (model.includes("opus")) return "Opus";
  if (model.includes("haiku")) return "Haiku";
  return "Sonnet";
}

function getPresetLabel(preset: string): string {
  if (preset === "read-only") return "Read Only";
  if (preset === "full") return "Full Access";
  if (preset === "standard") return "Standard";
  return "Custom";
}

function getContextSummary(context: Assistant["context"]): string {
  if (!context.length) return "No context";
  const counts: Record<string, number> = {};
  for (const item of context) {
    counts[item.type] = (counts[item.type] || 0) + 1;
  }
  const parts: string[] = [];
  if (counts.file) parts.push(`${counts.file} file${counts.file > 1 ? "s" : ""}`);
  if (counts.url) parts.push(`${counts.url} URL${counts.url > 1 ? "s" : ""}`);
  if (counts.text) parts.push(`${counts.text} text${counts.text > 1 ? "s" : ""}`);
  return parts.join(", ");
}

export default function AssistantCard({ assistant, onSpawn, onEdit, onDelete }: Props) {
  return (
    <div className="assistant-card">
      <div className="assistant-card-header">
        <div className="assistant-card-title">{assistant.name}</div>
        <div className="assistant-card-badges">
          <span className="badge badge-model">{getModelLabel(assistant.default_model)}</span>
          <span className="badge badge-perm">
            {getPresetLabel(assistant.default_permissions?.preset || "standard")}
          </span>
        </div>
      </div>
      {assistant.description && (
        <p className="assistant-card-description">{assistant.description}</p>
      )}
      {assistant.instructions && (
        <p className="assistant-card-instructions">
          {assistant.instructions.length > 120
            ? assistant.instructions.slice(0, 120) + "..."
            : assistant.instructions}
        </p>
      )}
      <div className="assistant-card-meta">
        <span className="assistant-card-context">{getContextSummary(assistant.context)}</span>
      </div>
      <div className="assistant-card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => onSpawn(assistant)}>
          Spawn Job
        </button>
        <button className="btn btn-secondary btn-sm" onClick={() => onEdit(assistant)}>
          Edit
        </button>
        <button className="btn btn-danger btn-sm" onClick={() => onDelete(assistant.id)}>
          Delete
        </button>
      </div>
    </div>
  );
}
