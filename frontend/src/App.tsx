import React, { useEffect, useState, useCallback } from "react";
import { api, Job, Project, Assistant, Schedule, Permissions } from "./api";
import { socket } from "./socket";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import AgentGrid from "./components/AgentGrid";
import JobForm from "./components/JobForm";
import AssistantList from "./components/AssistantList";
import AssistantForm from "./components/AssistantForm";
import ScheduleList from "./components/ScheduleList";
import AgentFlowView from "./components/AgentFlowView";

export interface JobPrefill {
  title: string;
  prompt: string;
  model: string;
  workDir: string;
  projectId: string;
  permissions: Permissions;
  assistantId: string;
  parentJobId: string;
}

export default function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [showJobForm, setShowJobForm] = useState(false);
  const [view, setView] = useState<"jobs" | "assistants" | "schedules" | "agentflow">("jobs");
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [showAssistantForm, setShowAssistantForm] = useState(false);
  const [editingAssistant, setEditingAssistant] = useState<Assistant | null>(null);
  const [jobPrefill, setJobPrefill] = useState<Partial<JobPrefill> | null>(null);

  const loadJobs = useCallback(async () => {
    const data = await api.jobs.list(selectedProject || undefined);
    setJobs(data);
  }, [selectedProject]);

  const loadProjects = useCallback(async () => {
    const data = await api.projects.list();
    setProjects(data);
  }, []);

  const loadAssistants = useCallback(async () => {
    const data = await api.assistants.list();
    setAssistants(data);
  }, []);

  const loadSchedules = useCallback(async () => {
    const data = await api.schedules.list();
    setSchedules(data);
  }, []);

  useEffect(() => {
    loadJobs();
    loadProjects();
    loadAssistants();
    loadSchedules();
  }, [loadJobs, loadProjects, loadAssistants, loadSchedules]);

  // Real-time updates
  useEffect(() => {
    function onJobUpdated(data: { id: string; status: string }) {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === data.id ? { ...j, status: data.status, updated_at: new Date().toISOString() } : j
        )
      );
    }

    socket.on("job:updated", onJobUpdated);
    return () => {
      socket.off("job:updated", onJobUpdated);
    };
  }, []);

  // Poll every 5s for fresh data
  useEffect(() => {
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  async function handleCancel(id: string) {
    await api.jobs.cancel(id);
    loadJobs();
  }

  async function handleDelete(id: string) {
    await api.jobs.delete(id);
    loadJobs();
  }

  function handleSpawnFromAssistant(assistant: Assistant) {
    setJobPrefill({
      title: "",
      prompt: "",
      model: assistant.default_model,
      workDir: assistant.default_work_dir,
      projectId: assistant.default_project_id || "",
      permissions: assistant.default_permissions,
      assistantId: assistant.id,
    });
    setShowJobForm(true);
    setView("jobs");
  }

  function handleEditAssistant(assistant: Assistant) {
    setEditingAssistant(assistant);
    setShowAssistantForm(true);
  }

  async function handleDeleteAssistant(id: string) {
    await api.assistants.delete(id);
    loadAssistants();
  }

  return (
    <div className="app">
      <Header
        jobs={jobs}
        view={view}
        onViewChange={setView}
        onNewJob={() => {
          setJobPrefill(null);
          setShowJobForm(true);
        }}
        onNewAssistant={() => {
          setEditingAssistant(null);
          setShowAssistantForm(true);
        }}
        onNewSchedule={() => {
          setJobPrefill(null);
          setShowJobForm(true);
        }}
      />
      <div className="main-layout">
        <Sidebar
          projects={projects}
          selectedProject={selectedProject}
          onSelectProject={setSelectedProject}
          onProjectsChange={loadProjects}
          jobs={jobs}
        />
        <main className="content">
          {view === "jobs" ? (
            <AgentGrid
              jobs={jobs}
              onCancel={handleCancel}
              onDelete={handleDelete}
              onNewJob={() => {
                setJobPrefill(null);
                setShowJobForm(true);
              }}
            />
          ) : view === "assistants" ? (
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
          ) : view === "agentflow" ? (
            <AgentFlowView
              selectedProject={selectedProject}
              onCancel={handleCancel}
              onDelete={handleDelete}
            />
          ) : (
            <ScheduleList
              schedules={schedules}
              onRefresh={() => {
                loadSchedules();
                loadJobs();
              }}
              onNewSchedule={() => {
                setJobPrefill(null);
                setShowJobForm(true);
              }}
            />
          )}
        </main>
      </div>
      {showJobForm && (
        <JobForm
          projects={projects}
          jobs={jobs}
          selectedProject={selectedProject}
          onClose={() => {
            setShowJobForm(false);
            setJobPrefill(null);
          }}
          onCreated={loadJobs}
          prefill={jobPrefill}
        />
      )}
      {showAssistantForm && (
        <AssistantForm
          projects={projects}
          assistant={editingAssistant}
          onClose={() => {
            setShowAssistantForm(false);
            setEditingAssistant(null);
          }}
          onSaved={loadAssistants}
        />
      )}
    </div>
  );
}
