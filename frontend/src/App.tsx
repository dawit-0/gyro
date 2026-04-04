import React, { useEffect, useState, useCallback } from "react";
import { api, Task, Flow, Agent, Permissions } from "./api";
import { socket } from "./socket";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import TaskForm from "./components/TaskForm";
import AgentList from "./components/AgentList";
import AgentForm from "./components/AgentForm";
import TaskFlowView from "./components/TaskFlowView";
import FlowDashboard from "./components/FlowDashboard";
import TaskDetailPage from "./components/TaskDetailPage";

export interface TaskPrefill {
  title: string;
  prompt: string;
  model: string;
  workDir: string;
  flowId: string;
  permissions: Permissions;
  agentId: string;
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [selectedFlow, setSelectedFlow] = useState<string | null>(null);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [view, setView] = useState<"flows" | "agents">("flows");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [showAgentForm, setShowAgentForm] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [taskPrefill, setTaskPrefill] = useState<Partial<TaskPrefill> | null>(null);
  const [showNewFlowForm, setShowNewFlowForm] = useState(false);
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<string | null>(null);

  const loadTasks = useCallback(async () => {
    const data = await api.tasks.list(selectedFlow || undefined);
    setTasks(data);
  }, [selectedFlow]);

  const loadFlows = useCallback(async () => {
    const data = await api.flows.list();
    setFlows(data);
  }, []);

  const loadAgents = useCallback(async () => {
    const data = await api.agents.list();
    setAgents(data);
  }, []);

  useEffect(() => {
    loadTasks();
    loadFlows();
    loadAgents();
  }, [loadTasks, loadFlows, loadAgents]);

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

  function handleSpawnFromAgent(agent: Agent) {
    setTaskPrefill({
      title: "",
      prompt: "",
      model: agent.default_model,
      workDir: agent.default_work_dir,
      flowId: agent.default_flow_id || "",
      permissions: agent.default_permissions,
      agentId: agent.id,
    });
    setShowTaskForm(true);
    setView("flows");
  }

  function handleEditAgent(agent: Agent) {
    setEditingAgent(agent);
    setShowAgentForm(true);
  }

  async function handleDeleteAgent(id: string) {
    await api.agents.delete(id);
    loadAgents();
  }

  function handleQuickTask() {
    setTaskPrefill({
      flowId: "__new__",
    });
    setShowTaskForm(true);
  }

  return (
    <div className="app">
      <Header
        tasks={tasks}
        view={view}
        onViewChange={(v) => {
          setView(v);
          if (v === "flows") setSelectedFlow(null);
        }}
        onNewFlow={() => {
          setSelectedFlow(null);
          setShowNewFlowForm(true);
        }}
        onNewAgent={() => {
          setEditingAgent(null);
          setShowAgentForm(true);
        }}
        onQuickTask={handleQuickTask}
      />
      <div className="main-layout">
        <Sidebar
          flows={flows}
          selectedFlow={selectedFlow}
          onSelectFlow={setSelectedFlow}
          onFlowsChange={loadFlows}
          tasks={tasks}
          view={view}
          agents={agents}
          onNewTask={() => {
            setTaskPrefill(null);
            setShowTaskForm(true);
          }}
          onNewAgent={() => {
            setEditingAgent(null);
            setShowAgentForm(true);
          }}
          onSpawnAgent={handleSpawnFromAgent}
          onEditAgent={handleEditAgent}
          onTriggerFlow={async (id) => {
            await api.flows.trigger(id);
            loadTasks();
          }}
          onRetryFlow={handleRetryFlow}
          onResumeFlow={handleResumeFlow}
          showNewFlowForm={showNewFlowForm}
          onShowNewFlowForm={setShowNewFlowForm}
        />
        <main className="content">
          {selectedTaskDetail ? (
            <TaskDetailPage
              taskId={selectedTaskDetail}
              onBack={() => setSelectedTaskDetail(null)}
              onCancel={handleCancel}
              onDelete={handleDelete}
              onTrigger={handleTrigger}
              onRetryTask={handleRetryTask}
            />
          ) : view === "agents" ? (
            <AgentList
              agents={agents}
              onSpawn={handleSpawnFromAgent}
              onEdit={handleEditAgent}
              onDelete={handleDeleteAgent}
              onNewAgent={() => {
                setEditingAgent(null);
                setShowAgentForm(true);
              }}
            />
          ) : selectedFlow ? (
            <TaskFlowView
              selectedFlow={selectedFlow}
              onCancel={handleCancel}
              onDelete={handleDelete}
              onTrigger={handleTrigger}
              onRetryTask={handleRetryTask}
              onRetryFlow={handleRetryFlow}
              onResumeFlow={handleResumeFlow}
              onViewTaskDetail={setSelectedTaskDetail}
            />
          ) : (
            <FlowDashboard
              flows={flows}
              tasks={tasks}
              onSelectFlow={setSelectedFlow}
              onNewFlow={() => setShowNewFlowForm(true)}
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
      {showAgentForm && (
        <AgentForm
          flows={flows}
          agent={editingAgent}
          onClose={() => {
            setShowAgentForm(false);
            setEditingAgent(null);
          }}
          onSaved={loadAgents}
        />
      )}
    </div>
  );
}
