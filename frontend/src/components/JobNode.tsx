import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";

export interface JobNodeData {
  title: string;
  status: string;
  model: string;
  [key: string]: unknown;
}

function JobNode({ data }: NodeProps) {
  const { title, status, model } = data as unknown as JobNodeData;
  const statusClass = status === "cancelled" ? "cancelled" : status;
  const modelShort = (model as string || "").replace("claude-", "").replace("-20250514", "").replace("-latest", "");

  return (
    <div className={`flow-node flow-node-${statusClass}`}>
      <Handle type="target" position={Position.Top} className="flow-handle" />
      <div className="flow-node-header">
        <span className="flow-node-title">{title as string}</span>
        <span className={`flow-node-status ${statusClass}`}>{status as string}</span>
      </div>
      <div className="flow-node-meta">{modelShort}</div>
      <Handle type="source" position={Position.Bottom} className="flow-handle" />
    </div>
  );
}

export default memo(JobNode);
