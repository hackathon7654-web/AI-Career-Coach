/**
 * ProofPath AI — Frontend API Client
 * Typed client communicating with FastAPI backend:
 * - Credentials included on all requests for HttpOnly session cookie authorization
 * - CSRF defense header (X-Requested-With)
 * - Safe response validation and detailed error extraction
 */

function resolveApiBase(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof window !== 'undefined' && window.location) {
    const currentHost = window.location.hostname;
    // When accessing via loopback, dynamically match the port 8001 host to current hostname (localhost vs 127.0.0.1)
    // to prevent cross-site cookie blocking with SameSite=lax.
    if (currentHost === '127.0.0.1' || currentHost === 'localhost') {
      if (envUrl) {
        try {
          const parsed = new URL(envUrl);
          if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') {
            parsed.hostname = currentHost;
            return parsed.origin;
          }
        } catch {
          // ignore parsing error
        }
      }
      return `http://${currentHost}:8001`;
    }
  }
  return envUrl || '';
}

export const API_BASE = resolveApiBase();

export interface ApiErrorResponse {
  detail: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  // Custom header for CSRF defense-in-depth on cookie requests
  headers.set('X-Requested-With', 'XMLHttpRequest');

  // Support Bearer/Header token fallback for cross-domain requests
  const sessionToken = sessionStore.getSessionToken();
  if (sessionToken && !headers.has('X-Session-Token')) {
    headers.set('X-Session-Token', sessionToken);
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${sessionToken}`);
    }
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // Includes HttpOnly proofpath_session cookie
  };

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    throw new ApiError(
      `Network connection failed. Ensure backend is running at ${API_BASE}.`,
      0
    );
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson && errJson.detail) {
        errorMessage = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // Fallback to status text
      if (response.statusText) errorMessage = response.statusText;
    }
    throw new ApiError(errorMessage, response.status);
  }

  return response.json() as Promise<T>;
}

// Session State Store
export const sessionStore = {
  getPortfolioId: (): string | null => localStorage.getItem('proofpath_portfolio_id'),
  setPortfolioId: (id: string) => localStorage.setItem('proofpath_portfolio_id', id),
  getJobId: (): string | null => localStorage.getItem('proofpath_job_id'),
  setJobId: (id: string) => localStorage.setItem('proofpath_job_id', id),
  getRunId: (): string | null => localStorage.getItem('proofpath_run_id'),
  setRunId: (id: string) => localStorage.setItem('proofpath_run_id', id),
  getSessionToken: (): string | null => localStorage.getItem('proofpath_session_token'),
  setSessionToken: (token: string) => localStorage.setItem('proofpath_session_token', token),
  clear: () => {
    localStorage.removeItem('proofpath_portfolio_id');
    localStorage.removeItem('proofpath_job_id');
    localStorage.removeItem('proofpath_run_id');
    localStorage.removeItem('proofpath_session_token');
  },
};

// API Client Methods
export const api = {
  // Session Authentication Check
  async getSession() {
    return request<{
      authenticated: boolean;
      portfolio_id: string;
      github_username: string;
    }>('/api/portfolio/session');
  },

  // System & Integration Health Check
  async getHealth() {
    return request<{
      status: string;
      application: string;
      version: string;
      environment: string;
      timestamp: string;
      database: string;
      llm: string;
      github: string;
    }>('/api/health');
  },

  // Screen 1: Candidate Intake
  async createIntake(github_username: string) {
    const res = await request<{
      portfolio_id: string;
      github_username: string;
      profile_url: string;
      scan_status: string;
      created_at: string;
      session_token?: string;
    }>('/api/portfolio/intake', {
      method: 'POST',
      body: JSON.stringify({ github_username }),
    });
    sessionStore.setPortfolioId(res.portfolio_id);
    if (res.session_token) {
      sessionStore.setSessionToken(res.session_token);
    }
    return res;
  },

  // Screen 2: Repositories Discovery & Selection
  async discoverRepositories(portfolio_id: string, page = 1, per_page = 30) {
    return request<{
      portfolio_id: string;
      github_username: string;
      page: number;
      per_page: number;
      total_discovered: number;
      repositories: Array<{
        id?: string;
        name: string;
        full_name: string;
        html_url: string;
        description?: string;
        default_branch: string;
        language?: string;
        stars: number;
        is_eligible: boolean;
        skip_reason?: string;
        is_selected: boolean;
        last_commit_sha?: string;
      }>;
    }>(`/api/portfolio/${portfolio_id}/repositories/discover?page=${page}&per_page=${per_page}`);
  },

  async selectRepositories(portfolio_id: string, repository_ids: string[]) {
    return request<{
      portfolio_id: string;
      selected_count: number;
      repositories: any[];
    }>(`/api/portfolio/${portfolio_id}/repositories/select`, {
      method: 'PATCH',
      body: JSON.stringify({ repository_ids }),
    });
  },

  // Screen 3: Job Ingestion
  async createJob(params: { job_url?: string; pasted_text?: string; portfolio_id?: string }) {
    const res = await request<{
      id: string;
      source_url?: string;
      provenance: 'fetched' | 'user_pasted';
      title: string;
      company?: string;
      requirements: any[];
      retrieval_timestamp: string;
      limitations?: string;
      created_at: string;
    }>('/api/jobs', {
      method: 'POST',
      body: JSON.stringify(params),
    });
    sessionStore.setJobId(res.id);
    return res;
  },

  async getJob(job_id: string) {
    return request<{
      id: string;
      source_url?: string;
      provenance: 'fetched' | 'user_pasted';
      raw_text?: string;
      title: string;
      company?: string;
      requirements: any[];
      retrieval_timestamp: string;
      limitations?: string;
      created_at: string;
    }>(`/api/jobs/${job_id}`);
  },

  // Screen 4: Requirements Review & Update
  async getJobRequirements(job_id: string) {
    return request<any[]>(`/api/jobs/${job_id}/requirements`);
  },

  async updateJobRequirements(job_id: string, requirements: any[]) {
    return request<{
      job_id: string;
      requirements_count: number;
      requirements: any[];
    }>(`/api/jobs/${job_id}/requirements`, {
      method: 'PATCH',
      body: JSON.stringify({ requirements }),
    });
  },

  // Screen 5: Repository Scanning & Telemetry
  async triggerScan(portfolio_id: string, repository_ids?: string[]) {
    return request<any>(`/api/portfolio/${portfolio_id}/scan`, {
      method: 'POST',
      body: JSON.stringify(repository_ids ? { repository_ids } : {}),
    });
  },

  async getScanStatus(portfolio_id: string) {
    return request<{
      portfolio_id: string;
      portfolio_status: string;
      total_repositories_selected: number;
      scans_completed: number;
      scans_running: number;
      scans_failed: number;
      total_evidence_count: number;
      scans: Array<{
        scan_id: string;
        repository_id: string;
        repository_name: string;
        commit_sha: string;
        status: string;
        files_processed: number;
        total_files: number;
        skipped_summary?: string;
        duration_ms?: number;
        started_at: string;
        completed_at?: string;
      }>;
    }>(`/api/portfolio/${portfolio_id}/scan/status`);
  },

  // Screen 8: Evidence Citations
  async getEvidence(portfolio_id: string) {
    return request<{
      portfolio_id: string;
      total_count: number;
      evidence: Array<{
        id: string;
        scan_id: string;
        repository_id: string;
        repository_name?: string;
        canonical_skill: string;
        file_path: string;
        line_start?: number;
        line_end?: number;
        line_range?: string;
        commit_sha: string;
        explanation: string;
        evidence_type: string;
        ast_node_type?: string;
        snippet?: string;
        limitations?: string;
        created_at: string;
      }>;
    }>(`/api/portfolio/${portfolio_id}/evidence`);
  },

  // Screen 7: Evidence-Based Assessment
  async runAssessment(portfolio_id: string, job_id: string, trigger_type = 'initial_scan') {
    const res = await request<any>(`/api/portfolio/${portfolio_id}/assess/${job_id}?trigger_type=${trigger_type}`, {
      method: 'POST',
    });
    if (res && res.id) {
      sessionStore.setRunId(res.id);
    }
    return res;
  },

  async getAssessment(portfolio_id: string, run_id: string) {
    return request<any>(`/api/portfolio/${portfolio_id}/assessments/${run_id}`);
  },

  // Screen 10: History Ledger
  async listAssessments(portfolio_id: string, job_id?: string) {
    const qs = job_id ? `?job_id=${job_id}` : '';
    return request<{
      portfolio_id: string;
      total_runs: number;
      runs: Array<{
        id: string;
        portfolio_id: string;
        job_id: string;
        job_title?: string;
        snapshot_number: number;
        trigger_type: string;
        commit_references: Record<string, string>;
        status_summary: {
          demonstrated_count: number;
          partially_demonstrated_count: number;
          not_demonstrated_in_scope_count: number;
          uncertain_count: number;
          total_requirements: number;
          scanned_repositories_count: number;
          total_evidence_count: number;
        };
        created_at: string;
      }>;
    }>(`/api/portfolio/${portfolio_id}/assessments${qs}`);
  },

  // Screen 11: Snapshot Comparison Matrix
  async compareAssessments(portfolio_id: string, base_run_id: string, target_run_id: string) {
    return request<{
      portfolio_id: string;
      base_run_id: string;
      base_snapshot_number: number;
      base_created_at: string;
      target_run_id: string;
      target_snapshot_number: number;
      target_created_at: string;
      job_id: string;
      job_title?: string;
      transitions: Array<{
        requirement_id: string;
        skill_name: string;
        category: string;
        base_status?: string;
        target_status: string;
        status_changed: boolean;
        evidence_delta_count: number;
        explanation: string;
      }>;
      summary_delta: Record<string, number>;
      limitations?: string;
    }>(`/api/portfolio/${portfolio_id}/assessments/compare?base_run_id=${base_run_id}&target_run_id=${target_run_id}`);
  },

  // Screen 8: GitHub Activity & Webhook Deliveries
  async getActivity(portfolio_id: string) {
    return request<{
      portfolio_id: string;
      deliveries: Array<{
        id?: string;
        delivery_id: string;
        repository_name: string;
        event_type: string;
        commit_sha: string;
        changed_paths: string[];
        received_at: string;
        hmac_verified: boolean;
        status: string;
        reassessment_run_id?: string;
        retry_count: number;
        error_details?: string;
        created_at?: string;
      }>;
    }>(`/api/portfolio/${portfolio_id}/activity`);
  },

  async simulatePush(
    portfolio_id: string,
    params: {
      repository_name: string;
      commit_sha?: string;
      commit_message?: string;
      changed_paths?: string[];
    }
  ) {
    return request<{
      delivery_id: string;
      status: string;
      repository?: string;
      commit_sha?: string;
      reassessment_run_id?: string;
      message: string;
    }>(`/api/portfolio/${portfolio_id}/simulate-push`, {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },
};
