import React, { useState } from "react";
import { api } from "../api";

interface Props {
  onClose: () => void;
  onCreated: (flowId: string) => void;
}

export default function NewFlowModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [schedule, setSchedule] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const flow = await api.flows.create({
        name: name.trim(),
        description: description.trim() || undefined,
        schedule: schedule.trim() || undefined,
      });
      onCreated(flow.id);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 460 }}>
        <h2>New Flow</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Flow name"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label>Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this flow do?"
              rows={3}
            />
          </div>

          <div className="form-group">
            <label>Schedule (optional)</label>
            <input
              value={schedule}
              onChange={(e) => setSchedule(e.target.value)}
              placeholder="Cron expression, e.g. 0 9 * * *"
            />
            {schedule && (
              <p className="field-hint">
                Cron: minute hour day-of-month month day-of-week
              </p>
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
              {submitting ? "Creating..." : "Create Flow"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
