import React from "react";
import { api, Schedule } from "../api";

interface Props {
  schedules: Schedule[];
  onRefresh: () => void;
  onNewSchedule: () => void;
}

function formatTime(iso: string | null): string {
  if (!iso) return "--";
  return new Date(iso).toLocaleString();
}

function describeCron(expr: string): string {
  const presets: Record<string, string> = {
    "0 * * * *": "Every hour",
    "0 9 * * *": "Daily at 9:00 AM",
    "0 9 * * 1-5": "Weekdays at 9:00 AM",
    "0 9 * * 1": "Weekly on Monday at 9:00 AM",
    "0 9 1 * *": "Monthly on 1st at 9:00 AM",
    "* * * * *": "Every minute",
  };
  return presets[expr] || expr;
}

export default function ScheduleList({ schedules, onRefresh, onNewSchedule }: Props) {
  async function handleToggle(id: string, enabled: boolean) {
    await api.schedules.update(id, { enabled: !enabled });
    onRefresh();
  }

  async function handleTrigger(id: string) {
    await api.schedules.trigger(id);
    onRefresh();
  }

  async function handleDelete(id: string) {
    await api.schedules.delete(id);
    onRefresh();
  }

  if (schedules.length === 0) {
    return (
      <div className="empty-state">
        <h3>No Schedules</h3>
        <p>Create a recurring schedule to automatically run jobs on a cadence.</p>
        <button className="btn btn-primary" onClick={onNewSchedule}>
          + New Schedule
        </button>
      </div>
    );
  }

  return (
    <div className="schedule-grid">
      {schedules.map((s) => (
        <div key={s.id} className={`schedule-card${s.enabled ? "" : " disabled"}`}>
          <div className="schedule-card-header">
            <h3>{s.name}</h3>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={() => handleToggle(s.id, s.enabled)}
              />
              <span className="toggle-slider" />
            </label>
          </div>

          <div className="schedule-card-cron">
            {describeCron(s.cron_expression)}
          </div>

          <div className="schedule-card-meta">
            <div>
              <span className="meta-label">Next run:</span>{" "}
              {s.enabled ? formatTime(s.next_run_at) : "Paused"}
            </div>
            <div>
              <span className="meta-label">Last run:</span>{" "}
              {formatTime(s.last_run_at)}
            </div>
            <div>
              <span className="meta-label">Model:</span>{" "}
              {s.model.includes("opus") ? "Opus" : s.model.includes("haiku") ? "Haiku" : "Sonnet"}
            </div>
          </div>

          <div className="schedule-card-prompt">
            {s.prompt.length > 120 ? s.prompt.slice(0, 120) + "..." : s.prompt}
          </div>

          <div className="schedule-card-actions">
            <button
              className="btn btn-sm btn-primary"
              onClick={() => handleTrigger(s.id)}
              title="Run now"
            >
              Trigger Now
            </button>
            <button
              className="btn btn-sm btn-danger"
              onClick={() => handleDelete(s.id)}
            >
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
