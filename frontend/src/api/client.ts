const API_BASE = "/api";

export interface Source {
  id: number;
  topic_id: number;
  url: string;
  name: string;
  status: string;
}

export interface TopicPreference {
  id: number;
  topic_id: number;
}

export interface Me {
  email: string;
  is_admin: boolean;
  user_id: number | null;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.statusText}`);
  }
  return response.json();
}

export function loginUrl(): string {
  return `${API_BASE}/auth/login`;
}

export async function getMe(): Promise<Me | null> {
  try {
    return await request<Me>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}

export async function logout(): Promise<void> {
  await request("/auth/logout", { method: "POST" });
}

export async function listPendingSources(): Promise<Source[]> {
  return request("/admin/sources");
}

export async function listMyPreferences(): Promise<TopicPreference[]> {
  return request("/me/preferences");
}
