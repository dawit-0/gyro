import React from "react";
import { Assistant } from "../api";
import AssistantCard from "./AssistantCard";

interface Props {
  assistants: Assistant[];
  onSpawn: (assistant: Assistant) => void;
  onEdit: (assistant: Assistant) => void;
  onDelete: (id: string) => void;
  onNewAssistant: () => void;
}

export default function AssistantList({ assistants, onSpawn, onEdit, onDelete, onNewAssistant }: Props) {
  if (!assistants.length) {
    return (
      <div className="empty-state">
        <p>No assistants yet</p>
        <p className="text-muted">
          Create pre-configured assistants with instructions and context to quickly spawn jobs.
        </p>
        <button className="btn btn-primary" onClick={onNewAssistant}>
          + New Assistant
        </button>
      </div>
    );
  }

  return (
    <div className="assistant-grid">
      {assistants.map((a) => (
        <AssistantCard
          key={a.id}
          assistant={a}
          onSpawn={onSpawn}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
