import type {
  AnalysisResult,
  AnalyticsResponse,
  GithubIssue,
  IncidentDetail,
  IncidentListResponse,
  IncidentReport,
  UploadResponse,
} from "@blackbox/schemas";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(
      `Cannot reach the BlackBox API at ${API_BASE}. Is the backend running?`,
      0,
    );
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = undefined;
    }
    throw new ApiError(
      `API request failed (${response.status})`,
      response.status,
      detail,
    );
  }
  return (await response.json()) as T;
}

export interface IncidentListParams {
  robot_id?: string;
  severity?: string;
  outcome?: string;
  failure_category?: string;
  start_after?: string;
  start_before?: string;
  limit?: number;
  offset?: number;
}

export function fetchIncidents(
  params: IncidentListParams = {},
): Promise<IncidentListResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<IncidentListResponse>(`/api/incidents${suffix}`);
}

export function fetchIncidentDetail(id: string): Promise<IncidentDetail> {
  return request<IncidentDetail>(`/api/incidents/${encodeURIComponent(id)}`);
}

export function fetchAnalysis(id: string): Promise<AnalysisResult> {
  return request<AnalysisResult>(
    `/api/incidents/${encodeURIComponent(id)}/analysis`,
  );
}

export function fetchReport(id: string): Promise<IncidentReport> {
  return request<IncidentReport>(
    `/api/incidents/${encodeURIComponent(id)}/report`,
  );
}

export function fetchGithubIssue(
  id: string,
  repo?: string,
): Promise<GithubIssue> {
  const suffix = repo ? `?repo=${encodeURIComponent(repo)}` : "";
  return request<GithubIssue>(
    `/api/incidents/${encodeURIComponent(id)}/github-issue${suffix}`,
  );
}

export function fetchAnalytics(): Promise<AnalyticsResponse> {
  return request<AnalyticsResponse>("/api/analytics");
}

export interface UploadFieldError {
  field: string;
  error: string;
}

/** Shape of the 422 detail returned by the upload endpoint. */
export interface UploadErrorDetail {
  message: string;
  errors: UploadFieldError[];
}

export async function uploadIncident(
  file: File,
  metadata?: string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (metadata && metadata.trim()) form.append("metadata", metadata.trim());

  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/incidents/upload`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError(
      `Cannot reach the BlackBox API at ${API_BASE}. Is the backend running?`,
      0,
    );
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(
      `Upload rejected (${response.status})`,
      response.status,
      detail,
    );
  }
  return (await response.json()) as UploadResponse;
}

export async function deleteIncident(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/incidents/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    );
  } catch {
    throw new ApiError(
      `Cannot reach the BlackBox API at ${API_BASE}. Is the backend running?`,
      0,
    );
  }
  if (!response.ok) {
    throw new ApiError(`Delete failed (${response.status})`, response.status);
  }
}
