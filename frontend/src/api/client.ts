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

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.statusText}`);
  }
  return response.json();
}

export async function listPendingSources(): Promise<Source[]> {
  return request("/admin/sources");
}

export async function listMyPreferences(): Promise<TopicPreference[]> {
  return request("/me/preferences");
}
