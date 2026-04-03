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

export interface Task {
  id: string;
  title: string;
  prompt: string;
  status: "active" | "paused";
  priority: number;
  model: string;
  work_dir: string;
  flow_id: string;
  assistant_id: string | null;
  permissions: Permissions;
  schedule: string | null;
  schedule_enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
  latest_run?: TaskRun | null;
}

export interface TaskRun {
  id: string;
  task_id: string;
  run_number: number;
  trigger: "manual" | "schedule" | "dependency" | "retry";
  status: "queued" | "running" | "success" | "failed" | "cancelled";
  pid: number | null;
  exit_code: number | null;
  cost_usd: number;
  duration_ms: number;
  num_turns: number;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  attempt_number: number;
  retry_of_run_id: string | null;
}

export interface TaskRunOutput {
  id: number;
  task_run_id: string;
  seq: number;
  type: string;
  content: string;
  timestamp: string;
}

export interface DagNode {
  id: string;
  title: string;
  status: string;
  model: string;
  schedule: string | null;
  max_retries: number;
  retry_delay_seconds: number;
  latest_run_status: string | null;
  latest_run_number: number | null;
  attempt_number: number | null;
  latest_run_trigger: string | null;
  created_at: string;
  updated_at: string;
}

export interface DagEdge {
  source: string;
  target: string;
}

export interface DagGraph {
  nodes: DagNode[];
  edges: DagEdge[];
}

export interface Flow {
  id: string;
  name: string;
  description: string;
  schedule: string | null;
  schedule_enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
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
  default_flow_id: string | null;
  created_at: string;
  updated_at: string;
}

export const api = {
  tasks: {
    list: (flowId?: string) =>
      request<Task[]>(`/tasks${flowId ? `?flow_id=${flowId}` : ""}`),
    get: (id: string) => request<Task>(`/tasks/${id}`),
    create: (data: {
      title: string;
      prompt: string;
      model?: string;
      priority?: number;
      work_dir?: string;
      flow_id?: string;
      permissions?: Permissions;
      schedule?: string;
      assistant_id?: string;
      depends_on?: string[];
      max_retries?: number;
      retry_delay_seconds?: number;
    }) => request<Task>("/tasks", { method: "POST", body: JSON.stringify(data) }),
    update: (
      id: string,
      data: Partial<{
        title: string;
        prompt: string;
        status: string;
        priority: number;
        model: string;
        work_dir: string;
        flow_id: string;
        permissions: Permissions;
        schedule: string;
        schedule_enabled: boolean;
      }>
    ) =>
      request<Task>(`/tasks/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    trigger: (id: string) =>
      request<TaskRun>(`/tasks/${id}/trigger`, { method: "POST" }),
    cancel: (id: string) =>
      request<{ ok: boolean }>(`/tasks/${id}/cancel`, { method: "POST" }),
    retry: (id: string) =>
      request<{ id: string; task_id: string; run_number: number }>(
        `/tasks/${id}/retry`,
        { method: "POST" }
      ),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" }),
    runs: (id: string) => request<TaskRun[]>(`/tasks/${id}/runs`),
    dag: (flowId?: string) =>
      request<DagGraph>(`/tasks/dag${flowId ? `?flow_id=${flowId}` : ""}`),
    dependencies: (id: string) =>
      request<{ task_id: string; depends_on: string[] }>(`/tasks/${id}/dependencies`),
    addDependencies: (taskId: string, dependsOn: string[]) =>
      request<{ ok: boolean }>(`/tasks/${taskId}/dependencies`, {
        method: "POST",
        body: JSON.stringify({ depends_on: dependsOn }),
      }),
    removeDependency: (taskId: string, depId: string) =>
      request<{ ok: boolean }>(`/tasks/${taskId}/dependencies/${depId}`, {
        method: "DELETE",
      }),
    quickCreate: (data: {
      title: string;
      prompt: string;
      model?: string;
      work_dir?: string;
      permissions?: Permissions;
      schedule?: string;
      max_retries?: number;
      retry_delay_seconds?: number;
      trigger?: boolean;
    }) => request<Task>("/tasks/quick", { method: "POST", body: JSON.stringify(data) }),
  },
  taskRuns: {
    list: (taskId?: string) =>
      request<TaskRun[]>(`/task-runs${taskId ? `?task_id=${taskId}` : ""}`),
    get: (id: string) => request<TaskRun>(`/task-runs/${id}`),
    output: (id: string) => request<TaskRunOutput[]>(`/task-runs/${id}/output`),
  },
  flows: {
    list: () => request<Flow[]>("/flows"),
    get: (id: string) => request<Flow>(`/flows/${id}`),
    create: (data: { name: string; description?: string; schedule?: string }) =>
      request<Flow>("/flows", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (
      id: string,
      data: Partial<{
        name: string;
        description: string;
        schedule: string;
        schedule_enabled: boolean;
      }>
    ) =>
      request<Flow>(`/flows/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ ok: boolean }>(`/flows/${id}`, { method: "DELETE" }),
    trigger: (id: string) =>
      request<{ triggered: number; runs: Array<{ id: string; task_id: string }> }>(
        `/flows/${id}/trigger`,
        { method: "POST" }
      ),
    retry: (id: string) =>
      request<{ retried: number; runs: Array<{ id: string; task_id: string }> }>(
        `/flows/${id}/retry`,
        { method: "POST" }
      ),
    resume: (id: string) =>
      request<{ retried: number; runs: Array<{ id: string; task_id: string }> }>(
        `/flows/${id}/resume`,
        { method: "POST" }
      ),
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
      default_flow_id?: string;
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
        default_flow_id: string;
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
        flow_id?: string;
        permissions?: Permissions;
        depends_on?: string[];
        trigger?: boolean;
      }
    ) =>
      request<Task>(`/assistants/${id}/spawn`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
};
