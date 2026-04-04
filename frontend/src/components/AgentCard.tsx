import React from "react";
import { Agent } from "../api";

interface Props {
  agent: Agent;
  onSpawn: (agent: Agent) => void;
  onEdit: (agent: Agent) => void;
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

function getContextSummary(context: Agent["context"]): string {
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

export default function AgentCard({ agent, onSpawn, onEdit, onDelete }: Props) {
  return (
    <div className="agent-card">
      <div className="agent-card-header">
        <div className="agent-card-title">{agent.name}</div>
        <div className="agent-card-badges">
          <span className="badge badge-model">{getModelLabel(agent.default_model)}</span>
          <span className="badge badge-perm">
            {getPresetLabel(agent.default_permissions?.preset || "standard")}
          </span>
        </div>
      </div>
      {agent.description && (
        <p className="agent-card-description">{agent.description}</p>
      )}
      {agent.instructions && (
        <p className="agent-card-instructions">
          {agent.instructions.length > 120
            ? agent.instructions.slice(0, 120) + "..."
            : agent.instructions}
        </p>
      )}
      <div className="agent-card-meta">
        <span className="agent-card-context">{getContextSummary(agent.context)}</span>
      </div>
      <div className="agent-card-actions">
        <button className="btn btn-primary btn-sm" onClick={() => onSpawn(agent)}>
          Spawn Task
        </button>
        <button className="btn btn-secondary btn-sm" onClick={() => onEdit(agent)}>
          Edit
        </button>
        <button className="btn btn-danger btn-sm" onClick={() => onDelete(agent.id)}>
          Delete
        </button>
      </div>
    </div>
  );
}
