import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";

export interface TaskNodeData {
  title: string;
  status: string;
  latestRunStatus: string | null;
  model: string;
  schedule: string | null;
  [key: string]: unknown;
}

function TaskNode({ data }: NodeProps) {
  const { title, latestRunStatus, model, schedule } = data as unknown as TaskNodeData;
  const displayStatus = latestRunStatus || "idle";
  const statusClass = displayStatus === "cancelled" ? "cancelled" : displayStatus;
  const modelShort = (model as string || "").replace("claude-", "").replace("-20250514", "").replace("-latest", "");

  return (
    <div className={`flow-node flow-node-${statusClass}`}>
      <Handle type="target" position={Position.Top} className="flow-handle" />
      <div className="flow-node-header">
        <span className="flow-node-title">
          {schedule && <span className="schedule-badge-sm" title={`Schedule: ${schedule}`}>&#x23f0; </span>}
          {title as string}
        </span>
        <span className={`flow-node-status ${statusClass}`}>{displayStatus as string}</span>
      </div>
      <div className="flow-node-meta">{modelShort}</div>
      <Handle type="source" position={Position.Bottom} className="flow-handle" />
    </div>
  );
}

export default memo(TaskNode);
