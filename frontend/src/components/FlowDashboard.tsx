import React from "react";
import { Flow, Task } from "../api";

interface Props {
  flows: Flow[];
  tasks: Task[];
  onSelectFlow: (id: string) => void;
  onNewFlow: () => void;
}

export default function FlowDashboard({ flows, tasks, onSelectFlow, onNewFlow }: Props) {
  function getFlowStats(flowId: string) {
    const flowTasks = tasks.filter((t) => t.flow_id === flowId);
    const running = flowTasks.filter((t) => t.latest_run?.status === "running").length;
    const failed = flowTasks.filter((t) => t.latest_run?.status === "failed").length;
    const success = flowTasks.filter((t) => t.latest_run?.status === "success").length;
    return { total: flowTasks.length, running, failed, success };
  }

  function getFlowStatus(flowId: string): "running" | "failed" | "success" | "idle" {
    const stats = getFlowStats(flowId);
    if (stats.running > 0) return "running";
    if (stats.failed > 0) return "failed";
    if (stats.success > 0 && stats.success === stats.total) return "success";
    return "idle";
  }

  if (flows.length === 0) {
    return (
      <div className="flow-dashboard-empty">
        <div className="flow-dashboard-empty-content">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <rect x="4" y="8" width="40" height="32" rx="4" stroke="var(--text-muted)" strokeWidth="2" />
            <path d="M24 18v12M18 24h12" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <h3>No flows yet</h3>
          <p>Create a flow to organize and run your tasks.</p>
          <button className="btn btn-primary" onClick={onNewFlow}>
            + New Flow
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flow-dashboard">
      <div className="flow-dashboard-grid">
        {flows.map((flow) => {
          const stats = getFlowStats(flow.id);
          const status = getFlowStatus(flow.id);
          return (
            <div
              key={flow.id}
              className={`flow-card flow-card-${status}`}
              onClick={() => onSelectFlow(flow.id)}
            >
              <div className="flow-card-header">
                <span className={`flow-card-dot flow-card-dot-${status}`} />
                <h3 className="flow-card-name">{flow.name}</h3>
              </div>
              {flow.description && (
                <p className="flow-card-desc">{flow.description}</p>
              )}
              <div className="flow-card-stats">
                <span className="flow-card-stat">
                  {stats.total} task{stats.total !== 1 ? "s" : ""}
                </span>
                {stats.running > 0 && (
                  <span className="flow-card-stat flow-card-stat-running">
                    {stats.running} running
                  </span>
                )}
                {stats.failed > 0 && (
                  <span className="flow-card-stat flow-card-stat-failed">
                    {stats.failed} failed
                  </span>
                )}
              </div>
              <div className="flow-card-footer">
                {flow.schedule && (
                  <span className="flow-card-schedule">&#x23f0; {flow.schedule}</span>
                )}
                {flow.last_run_at && (
                  <span className="flow-card-time">
                    Last run {new Date(flow.last_run_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
