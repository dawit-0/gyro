import React, { useEffect, useState, useCallback } from "react";
import { api, Task, Flow, Assistant, Permissions } from "./api";
import { socket } from "./socket";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import TaskForm from "./components/TaskForm";
import AssistantList from "./components/AssistantList";
import AssistantForm from "./components/AssistantForm";
import TaskFlowView from "./components/TaskFlowView";

export interface TaskPrefill {
  title: string;
  prompt: string;
  model: string;
  workDir: string;
  flowId: string;
  permissions: Permissions;
  assistantId: string;
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [selectedFlow, setSelectedFlow] = useState<string | null>(null);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [view, setView] = useState<"flows" | "assistants">("flows");
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [showAssistantForm, setShowAssistantForm] = useState(false);
  const [editingAssistant, setEditingAssistant] = useState<Assistant | null>(null);
  const [taskPrefill, setTaskPrefill] = useState<Partial<TaskPrefill> | null>(null);
  const [showQuickTask, setShowQuickTask] = useState(false);

  const loadTasks = useCallback(async () => {
    const data = await api.tasks.list(selectedFlow || undefined);
    setTasks(data);
  }, [selectedFlow]);

  const loadFlows = useCallback(async () => {
    const data = await api.flows.list();
    setFlows(data);
  }, []);

  const loadAssistants = useCallback(async () => {
    const data = await api.assistants.list();
    setAssistants(data);
  }, []);

  useEffect(() => {
    loadTasks();
    loadFlows();
    loadAssistants();
  }, [loadTasks, loadFlows, loadAssistants]);

  // Real-time updates
  useEffect(() => {
    function onTaskUpdated(data: { id: string; latest_run_status: string }) {
      loadTasks();
    }

    socket.on("task:updated", onTaskUpdated);
    return () => {
      socket.off("task:updated", onTaskUpdated);
    };
  }, [loadTasks]);

  // Poll every 5s for fresh data
  useEffect(() => {
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  async function handleCancel(id: string) {
    await api.tasks.cancel(id);
    loadTasks();
  }

  async function handleDelete(id: string) {
    await api.tasks.delete(id);
    loadTasks();
  }

  async function handleTrigger(id: string) {
    await api.tasks.trigger(id);
    loadTasks();
  }

  async function handleRetryTask(id: string) {
    await api.tasks.retry(id);
    loadTasks();
  }

  async function handleRetryFlow(id: string) {
    await api.flows.retry(id);
    loadTasks();
  }

  async function handleResumeFlow(id: string) {
    await api.flows.resume(id);
    loadTasks();
  }

  function handleSpawnFromAssistant(assistant: Assistant) {
    setTaskPrefill({
      title: "",
      prompt: "",
      model: assistant.default_model,
      workDir: assistant.default_work_dir,
      flowId: assistant.default_flow_id || "",
      permissions: assistant.default_permissions,
      assistantId: assistant.id,
    });
    setShowTaskForm(true);
    setView("flows");
  }

  function handleEditAssistant(assistant: Assistant) {
    setEditingAssistant(assistant);
    setShowAssistantForm(true);
  }

  async function handleDeleteAssistant(id: string) {
    await api.assistants.delete(id);
    loadAssistants();
  }

  async function handleQuickTask(title: string, prompt: string) {
    await api.tasks.quickCreate({ title, prompt, trigger: true });
    loadTasks();
    loadFlows();
    setShowQuickTask(false);
  }

  return (
    <div className="app">
      <Header
        tasks={tasks}
        view={view}
        onViewChange={setView}
        onNewTask={() => {
          setTaskPrefill(null);
          setShowTaskForm(true);
        }}
        onNewAssistant={() => {
          setEditingAssistant(null);
          setShowAssistantForm(true);
        }}
        onQuickTask={() => setShowQuickTask(true)}
      />
      <div className="main-layout">
        <Sidebar
          flows={flows}
          selectedFlow={selectedFlow}
          onSelectFlow={setSelectedFlow}
          onFlowsChange={loadFlows}
          tasks={tasks}
          view={view}
          assistants={assistants}
          onNewTask={() => {
            setTaskPrefill(null);
            setShowTaskForm(true);
          }}
          onNewAssistant={() => {
            setEditingAssistant(null);
            setShowAssistantForm(true);
          }}
          onSpawnAssistant={handleSpawnFromAssistant}
          onEditAssistant={handleEditAssistant}
          onTriggerFlow={async (id) => {
            await api.flows.trigger(id);
            loadTasks();
          }}
          onRetryFlow={handleRetryFlow}
          onResumeFlow={handleResumeFlow}
          onQuickTask={() => setShowQuickTask(true)}
        />
        <main className="content">
          {view === "assistants" ? (
            <AssistantList
              assistants={assistants}
              onSpawn={handleSpawnFromAssistant}
              onEdit={handleEditAssistant}
              onDelete={handleDeleteAssistant}
              onNewAssistant={() => {
                setEditingAssistant(null);
                setShowAssistantForm(true);
              }}
            />
          ) : (
            <TaskFlowView
              selectedFlow={selectedFlow}
              onCancel={handleCancel}
              onDelete={handleDelete}
              onTrigger={handleTrigger}
              onRetryTask={handleRetryTask}
              onRetryFlow={handleRetryFlow}
              onResumeFlow={handleResumeFlow}
            />
          )}
        </main>
      </div>
      {showTaskForm && (
        <TaskForm
          flows={flows}
          tasks={tasks}
          selectedFlow={selectedFlow}
          onClose={() => {
            setShowTaskForm(false);
            setTaskPrefill(null);
          }}
          onCreated={() => {
            loadTasks();
            loadFlows();
          }}
          prefill={taskPrefill}
        />
      )}
      {showAssistantForm && (
        <AssistantForm
          flows={flows}
          assistant={editingAssistant}
          onClose={() => {
            setShowAssistantForm(false);
            setEditingAssistant(null);
          }}
          onSaved={loadAssistants}
        />
      )}
      {showQuickTask && (
        <QuickTaskModal
          onClose={() => setShowQuickTask(false)}
          onSubmit={handleQuickTask}
        />
      )}
    </div>
  );
}

function QuickTaskModal({ onClose, onSubmit }: { onClose: () => void; onSubmit: (title: string, prompt: string) => void }) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !prompt.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit(title.trim(), prompt.trim());
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Quick Task</h2>
        <p style={{ color: "var(--text-secondary)", marginBottom: 16, fontSize: 13 }}>
          Creates a new flow with a single task and runs it immediately.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Brief description"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>Prompt</label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Instructions for the agent..."
            />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !title.trim() || !prompt.trim()}
            >
              {submitting ? "Creating..." : "Create & Run"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
