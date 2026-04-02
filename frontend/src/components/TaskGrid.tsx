import React from "react";
import { Task } from "../api";
import TaskCard from "./TaskCard";

interface Props {
  tasks: Task[];
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onTrigger: (id: string) => void;
  onNewTask: () => void;
}

export default function TaskGrid({ tasks, onCancel, onDelete, onTrigger, onNewTask }: Props) {
  if (tasks.length === 0) {
    return (
      <div className="empty-state">
        <h2>No tasks yet</h2>
        <p>Create a task to get started. Tasks can run on a schedule or be triggered manually.</p>
        <button className="btn btn-primary" onClick={onNewTask}>
          + New Task
        </button>
      </div>
    );
  }

  return (
    <div className="task-grid">
      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          tasks={tasks}
          onCancel={onCancel}
          onDelete={onDelete}
          onTrigger={onTrigger}
        />
      ))}
    </div>
  );
}
