const API_BASE = "/api";

export interface Source {
  id: number;
  topic_id: number;
  url: string;
  name: string;
  status: string;
}

export interface TopicPreference {
  topic_id: number;
  name: string;
  subscribed: boolean;
}

export interface Me {
  email: string;
  is_admin: boolean;
  user_id: number | null;
}

export interface FieldOption {
  id: number;
  name: string;
}

export interface RoleOption {
  id: number;
  name: string;
}

export interface Profile {
  field_name: string | null;
  role_name: string | null;
}

export interface ProfileUpdate {
  fieldName: string;
  fieldIsOther: boolean;
  roleName: string;
  roleIsOther: boolean;
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

export async function updateMyPreferences(topicIds: number[]): Promise<TopicPreference[]> {
  return request("/me/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic_ids: topicIds }),
  });
}

export async function setSourceStatus(sourceId: number, status: "approved" | "rejected"): Promise<Source> {
  return request(`/admin/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
}

export async function listFields(): Promise<FieldOption[]> {
  return request("/me/fields");
}

export async function listRoles(fieldId: number): Promise<RoleOption[]> {
  return request(`/me/fields/${fieldId}/roles`);
}

export async function updateMyProfile(update: ProfileUpdate): Promise<Profile> {
  return request("/me/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      field_name: update.fieldName,
      field_is_other: update.fieldIsOther,
      role_name: update.roleName,
      role_is_other: update.roleIsOther,
    }),
  });
}
