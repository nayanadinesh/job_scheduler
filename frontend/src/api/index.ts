import { api } from './client';

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
}

export interface RetryPolicy {
  id: string;
  strategy: string;
  base_delay_s: number;
  max_attempts: number;
  max_delay_s: number;
}

export interface Queue {
  id: string;
  project_id: string;
  name: string;
  priority: number;
  concurrency_limit: number;
  is_paused: boolean;
  retry_policy: RetryPolicy | null;
  created_at: string;
}

export interface Job {
  id: string;
  type: string;
  status: string;
  priority: number;
  attempts: number;
  max_attempts: number;
  run_at: string | null;
  created_at: string;
  updated_at: string;
  dedup_key: string | null;
  worker_id: string | null;
  queue_id: string;
  payload: Record<string, unknown>;
}

export interface JobExecution {
  id: string;
  job_id: string;
  attempt_no: number;
  worker_id: string | null;
  status: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  error: string | null;
}

export interface JobLog {
  id: string;
  job_id: string;
  execution_id: string | null;
  ts: string;
  level: string;
  message: string;
}

export interface ScheduledJob {
  id: string;
  queue_id: string;
  name: string;
  cron_expr: string;
  job_type: string;
  job_payload: Record<string, unknown>;
  description: string | null;
  is_active: boolean;
  last_fired_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

export interface Metrics {
  queues: QueueStat[];
  totals: Record<string, number>;
  workers: { active: number; stopped: number; total: number };
}

export interface QueueStat {
  queue_id: string;
  queue_name: string;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  dead: number;
  scheduled: number;
  cancelled: number;
  total: number;
  avg_duration_ms: number | null;
  completed_executions: number;
}

export interface Worker {
  id: string;
  hostname: string;
  queue_ids: string[];
  status: string;
  last_heartbeat_at: string | null;
  started_at: string | null;
}

export type Schedule =
  | { kind: 'immediate' }
  | { kind: 'delay'; delay_s: number }
  | { kind: 'scheduled'; run_at: string }
  | { kind: 'batch'; count: number; delay_s?: number };

export interface SubmitJobInput {
  type: string;
  payload?: Record<string, unknown>;
  priority?: number;
  dedup_key?: string;
  schedule?: Schedule;
}

export interface CreateQueueInput {
  name: string;
  priority?: number;
  concurrency_limit?: number;
  retry_policy?: {
    strategy: string;
    base_delay_s: number;
    max_attempts: number;
    max_delay_s: number;
  };
}

export interface CreateScheduledJobInput {
  name: string;
  cron_expr: string;
  job_type: string;
  job_payload?: Record<string, unknown>;
  description?: string;
}

const unwrap = <T>(r: { data: { data: T } }) => r.data.data;

// ── Auth ──────────────────────────────────────────────────────────────
export const register = (email: string, password: string, org_name: string) =>
  api.post<{ data: AuthResponse }>('/api/v1/auth/register', { email, password, org_name }).then(unwrap);

export const login = (email: string, password: string) =>
  api.post<{ data: AuthResponse }>('/api/v1/auth/login', { email, password }).then(unwrap);

// ── Projects ──────────────────────────────────────────────────────────
export const listProjects = (): Promise<Project[]> =>
  api.get<{ data: Project[] }>('/api/v1/projects').then(unwrap);

export const createProject = (name: string): Promise<Project> =>
  api.post<{ data: Project }>('/api/v1/projects', { name }).then(unwrap);

export const deleteProject = (projectId: string): Promise<void> =>
  api.delete(`/api/v1/projects/${projectId}`).then(() => undefined);

// ── Queues ────────────────────────────────────────────────────────────
export const listQueues = (projectId: string): Promise<Queue[]> =>
  api.get<{ data: Queue[] }>(`/api/v1/projects/${projectId}/queues`).then(unwrap);

export const createQueue = (projectId: string, input: CreateQueueInput): Promise<Queue> =>
  api.post<{ data: Queue }>(`/api/v1/projects/${projectId}/queues`, input).then(unwrap);

export const pauseQueue = (queueId: string) =>
  api.post(`/api/v1/queues/${queueId}/pause`).then(unwrap);

export const resumeQueue = (queueId: string) =>
  api.post(`/api/v1/queues/${queueId}/resume`).then(unwrap);

export const deleteQueue = (queueId: string): Promise<void> =>
  api.delete(`/api/v1/queues/${queueId}`).then(() => undefined);

// ── Jobs ──────────────────────────────────────────────────────────────
export const listJobs = (queueId: string, status?: string): Promise<Job[]> =>
  api.get<{ data: Job[] }>(`/api/v1/queues/${queueId}/jobs`, {
    params: status ? { status } : {},
  }).then(unwrap);

export const submitJob = (queueId: string, input: SubmitJobInput): Promise<Job | Job[]> =>
  api.post<{ data: Job | Job[] }>(`/api/v1/queues/${queueId}/jobs`, input).then(unwrap);

export const cancelJob = (jobId: string) =>
  api.post(`/api/v1/jobs/${jobId}/cancel`).then(unwrap);

export const retryJob = (jobId: string) =>
  api.post(`/api/v1/jobs/${jobId}/retry`).then(unwrap);

export const getJobExecutions = (jobId: string): Promise<JobExecution[]> =>
  api.get<{ data: JobExecution[] }>(`/api/v1/jobs/${jobId}/executions`).then(unwrap);

export const getJobLogs = (jobId: string): Promise<JobLog[]> =>
  api.get<{ data: JobLog[] }>(`/api/v1/jobs/${jobId}/logs`).then(unwrap);

// ── Scheduled (cron) jobs ─────────────────────────────────────────────
export const listScheduledJobs = (queueId: string): Promise<ScheduledJob[]> =>
  api.get<{ data: ScheduledJob[] }>(`/api/v1/queues/${queueId}/scheduled-jobs`).then(unwrap);

export const createScheduledJob = (queueId: string, input: CreateScheduledJobInput): Promise<ScheduledJob> =>
  api.post<{ data: ScheduledJob }>(`/api/v1/queues/${queueId}/scheduled-jobs`, input).then(unwrap);

export const deleteScheduledJob = (sjId: string): Promise<void> =>
  api.delete(`/api/v1/scheduled-jobs/${sjId}`).then(() => undefined);

// ── Metrics & Workers ─────────────────────────────────────────────────
export const getMetrics = (): Promise<Metrics> =>
  api.get<{ data: Metrics }>('/api/v1/metrics').then(unwrap);

export const listWorkers = (): Promise<Worker[]> =>
  api.get<{ data: Worker[] }>('/api/v1/workers').then(unwrap);
