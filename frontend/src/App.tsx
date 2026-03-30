import React, { useEffect, useState, useCallback } from "react";
import { api, Job, Project } from "./api";
import { socket } from "./socket";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import AgentGrid from "./components/AgentGrid";
import JobForm from "./components/JobForm";

export default function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [showJobForm, setShowJobForm] = useState(false);

  const loadJobs = useCallback(async () => {
    const data = await api.jobs.list(selectedProject || undefined);
    setJobs(data);
  }, [selectedProject]);

  const loadProjects = useCallback(async () => {
    const data = await api.projects.list();
    setProjects(data);
  }, []);

  useEffect(() => {
    loadJobs();
    loadProjects();
  }, [loadJobs, loadProjects]);

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

  return (
    <div className="app">
      <Header jobs={jobs} onNewJob={() => setShowJobForm(true)} />
      <div className="main-layout">
        <Sidebar
          projects={projects}
          selectedProject={selectedProject}
          onSelectProject={setSelectedProject}
          onProjectsChange={loadProjects}
          jobs={jobs}
        />
        <main className="content">
          <AgentGrid
            jobs={jobs}
            onCancel={handleCancel}
            onDelete={handleDelete}
            onNewJob={() => setShowJobForm(true)}
          />
        </main>
      </div>
      {showJobForm && (
        <JobForm
          projects={projects}
          selectedProject={selectedProject}
          onClose={() => setShowJobForm(false)}
          onCreated={loadJobs}
        />
      )}
    </div>
  );
}
