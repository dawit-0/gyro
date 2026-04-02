import React, { useEffect, useState } from "react";
import { api, Agent, AgentOutput, DagNode } from "../api";

interface Props {
  node: DagNode;
  allNodes: DagNode[];
  upstreamIds: string[];
  downstreamIds: string[];
  onClose: () => void;
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onNodeSelect: (id: string) => void;
}

export default function FlowDetailPanel({
  node,
  allNodes,
  upstreamIds,
  downstreamIds,
  onClose,
  onCancel,
  onDelete,
  onNodeSelect,
}: Props) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [output, setOutput] = useState<AgentOutput[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const agents = await api.agents.list(node.id);
      if (cancelled) return;
      if (agents.length > 0) {
        const latest = agents[agents.length - 1];
        setAgent(latest);
        const out = await api.agents.output(latest.id);
        if (!cancelled) setOutput(out);
      } else {
        setAgent(null);
        setOutput([]);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [node.id]);

  const nodeMap = new Map(allNodes.map((n) => [n.id, n]));
  const isActive = node.status === "running" || node.status === "queued";

  return (
    <div className="flow-detail-panel">
      <div className="flow-detail-header">
        <h3>{node.title}</h3>
        <button className="btn-icon" onClick={onClose}>x</button>
      </div>

      <div className="flow-detail-status-row">
        <span className={`status-pill ${node.status}`}>{node.status}</span>
        <span className="flow-detail-model">{node.model}</span>
      </div>

      {agent && (
        <div className="flow-detail-timing">
          {agent.duration_ms > 0 && (
            <span>{(agent.duration_ms / 1000).toFixed(1)}s</span>
          )}
          {agent.cost_usd > 0 && (
            <span>${agent.cost_usd.toFixed(4)}</span>
          )}
          {agent.num_turns > 0 && (
            <span>{agent.num_turns} turns</span>
          )}
        </div>
      )}

      {(upstreamIds.length > 0 || downstreamIds.length > 0) && (
        <div className="flow-detail-deps">
          {upstreamIds.length > 0 && (
            <div className="flow-detail-dep-section">
              <span className="flow-detail-dep-label">Depends on</span>
              {upstreamIds.map((id) => {
                const n = nodeMap.get(id);
                return (
                  <button
                    key={id}
                    className="flow-detail-dep-link"
                    onClick={() => onNodeSelect(id)}
                  >
                    {n ? n.title : id.slice(0, 8)}
                  </button>
                );
              })}
            </div>
          )}
          {downstreamIds.length > 0 && (
            <div className="flow-detail-dep-section">
              <span className="flow-detail-dep-label">Downstream</span>
              {downstreamIds.map((id) => {
                const n = nodeMap.get(id);
                return (
                  <button
                    key={id}
                    className="flow-detail-dep-link"
                    onClick={() => onNodeSelect(id)}
                  >
                    {n ? n.title : id.slice(0, 8)}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {output.length > 0 && (
        <div className="flow-detail-output">
          <div className="flow-detail-dep-label">Output</div>
          <pre className="flow-detail-output-pre">
            {output
              .filter((o) => o.type === "assistant" || o.type === "text" || o.type === "result")
              .map((o) => o.content)
              .join("\n")}
          </pre>
        </div>
      )}

      {isActive && (
        <div className="flow-detail-actions">
          <button className="btn btn-sm btn-danger" onClick={() => onCancel(node.id)}>
            Cancel
          </button>
          <button className="btn btn-sm btn-secondary" onClick={() => onDelete(node.id)}>
            Delete
          </button>
        </div>
      )}
      {!isActive && (
        <div className="flow-detail-actions">
          <button className="btn btn-sm btn-secondary" onClick={() => onDelete(node.id)}>
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
