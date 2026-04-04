import React from "react";
import { Agent } from "../api";
import AgentCard from "./AgentCard";

interface Props {
  agents: Agent[];
  onSpawn: (agent: Agent) => void;
  onEdit: (agent: Agent) => void;
  onDelete: (id: string) => void;
  onNewAgent: () => void;
}

export default function AgentList({ agents, onSpawn, onEdit, onDelete, onNewAgent }: Props) {
  if (!agents.length) {
    return (
      <div className="empty-state">
        <p>No agents yet</p>
        <p className="text-muted">
          Create pre-configured agents with instructions and context to quickly spawn tasks.
        </p>
        <button className="btn btn-primary" onClick={onNewAgent}>
          + New Agent
        </button>
      </div>
    );
  }

  return (
    <div className="agent-grid">
      {agents.map((a) => (
        <AgentCard
          key={a.id}
          agent={a}
          onSpawn={onSpawn}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
