const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return res.json();
}

export interface Permissions {
  preset: string;
  file_read: boolean;
  file_write: boolean;
  bash: boolean;
  web_search: boolean;
  mcp: boolean;
}

export const PERMISSION_PRESETS: Record<string, Permissions> = {
  "read-only": {
    preset: "read-only",
    file_read: true,
    file_write: false,
    bash: false,
    web_search: false,
    mcp: false,
  },
  standard: {
    preset: "standard",
    file_read: true,
    file_write: true,
    bash: true,
    web_search: false,
    mcp: false,
  },
  full: {
    preset: "full",
    file_read: true,
    file_write: true,
    bash: true,
    web_search: true,
    mcp: true,
  },
};

export interface Job {
  id: string;
  title: string;
  prompt: string;
  status: string;
  priority: number;
  model: string;
  work_dir: string;
  project_id: string | null;
  permissions: Permissions;
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  job_id: string;
  pid: number | null;
  status: string;
  exit_code: number | null;
  cost_usd: number;
  duration_ms: number;
  num_turns: number;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
}

export interface AgentOutput {
  id: number;
  agent_id: string;
  seq: number;
  type: string;
  content: string;
  timestamp: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export interface ContextItem {
  type: "file" | "url" | "text";
  path?: string;
  url?: string;
  content?: string;
}

export interface Assistant {
  id: string;
  name: string;
  description: string;
  instructions: string;
  context: ContextItem[];
  default_model: string;
  default_permissions: Permissions;
  default_work_dir: string;
  default_project_id: string | null;
  created_at: string;
  updated_at: string;
}

export const api = {
  jobs: {
    list: (projectId?: string) =>
      request<Job[]>(`/jobs${projectId ? `?project_id=${projectId}` : ""}`),
    get: (id: string) => request<Job>(`/jobs/${id}`),
    create: (data: {
      title: string;
      prompt: string;
      model?: string;
      priority?: number;
      work_dir?: string;
      project_id?: string;
      permissions?: Permissions;
    }) => request<Job>("/jobs", { method: "POST", body: JSON.stringify(data) }),
    cancel: (id: string) =>
      request<{ ok: boolean }>(`/jobs/${id}/cancel`, { method: "POST" }),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/jobs/${id}`, { method: "DELETE" }),
  },
  agents: {
    list: (jobId?: string) =>
      request<Agent[]>(`/agents${jobId ? `?job_id=${jobId}` : ""}`),
    get: (id: string) => request<Agent>(`/agents/${id}`),
    output: (id: string) => request<AgentOutput[]>(`/agents/${id}/output`),
  },
  projects: {
    list: () => request<Project[]>("/projects"),
    create: (data: { name: string; description?: string }) =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/projects/${id}`, { method: "DELETE" }),
  },
  assistants: {
    list: () => request<Assistant[]>("/assistants"),
    get: (id: string) => request<Assistant>(`/assistants/${id}`),
    create: (data: {
      name: string;
      description?: string;
      instructions?: string;
      context?: ContextItem[];
      default_model?: string;
      default_permissions?: Permissions;
      default_work_dir?: string;
      default_project_id?: string;
    }) =>
      request<Assistant>("/assistants", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (
      id: string,
      data: Partial<{
        name: string;
        description: string;
        instructions: string;
        context: ContextItem[];
        default_model: string;
        default_permissions: Permissions;
        default_work_dir: string;
        default_project_id: string;
      }>
    ) =>
      request<Assistant>(`/assistants/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/assistants/${id}`, { method: "DELETE" }),
    spawn: (
      id: string,
      data: {
        title: string;
        prompt?: string;
        model?: string;
        priority?: number;
        work_dir?: string;
        project_id?: string;
        permissions?: Permissions;
      }
    ) =>
      request<Job>(`/assistants/${id}/spawn`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
};
