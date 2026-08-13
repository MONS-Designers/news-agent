const API_BASE = "/api";

export interface Source {
  id: number;
  topic_id: number;
  url: string;
  name: string;
  status: string;
}

export interface DigestEngagement {
  digest_id: number;
  user_email: string;
  date: string;
  sent_at: string | null;
  opened_at: string | null;
  articles_total: number;
  articles_clicked: number;
  clicked_article_titles: string[];
  preferences_clicked: boolean;
}

export interface PendingTaxonomySuggestion {
  id: number;
  kind: string;
  field_name: string | null;
  text: string;
  submission_count: number;
}

export interface TopicPreference {
  topic_id: number;
  name: string;
  subscribed: boolean;
}

export interface Subscription {
  unsubscribed: boolean;
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
  name: string;
  isCurated: boolean;
}

export interface Profile {
  field_name: string | null;
  role_name: string | null;
  experience_bucket: string | null;
  interest_free_text: string | null;
}

export interface ProfileUpdate {
  fieldName?: string;
  fieldIsOther?: boolean;
  roleName?: string;
  roleIsOther?: boolean;
  experienceBucket?: string | null;
  interestFreeText?: string;
}

export interface TopicSuggestions {
  // "pending_slow" is non-terminal like "pending" - the backend is still
  // working, but one of its two concurrent calls already failed and it is
  // waiting out the other's retries (GH #36). Keep polling through it.
  suggestion_status: "none" | "pending" | "pending_slow" | "ready" | "failed";
  suggested_topic_ids: number[] | null;
  suggested_new_topic_names: string[] | null;
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

export async function listDigestEngagement(): Promise<DigestEngagement[]> {
  return request("/admin/engagement");
}

export async function listPendingTaxonomySuggestions(): Promise<PendingTaxonomySuggestion[]> {
  return request("/admin/taxonomy");
}

export async function decideTaxonomySuggestion(
  suggestionId: number,
  status: "approved" | "rejected",
  name?: string,
): Promise<PendingTaxonomySuggestion> {
  return request(`/admin/taxonomy/${suggestionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(name === undefined ? { status } : { status, name }),
  });
}

export async function listMyPreferences(): Promise<TopicPreference[]> {
  return request("/me/preferences");
}

export async function updateMyPreferences(
  topicIds: number[],
  newTopicNames: string[] = [],
): Promise<TopicPreference[]> {
  return request("/me/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic_ids: topicIds, new_topic_names: newTopicNames }),
  });
}

export async function getMySubscription(): Promise<Subscription> {
  return request("/me/subscription");
}

export async function updateMySubscription(unsubscribed: boolean): Promise<Subscription> {
  return request("/me/subscription", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ unsubscribed }),
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

interface RoleOptionDto {
  name: string;
  is_curated: boolean;
}

export async function listRoles(fieldId: number): Promise<RoleOption[]> {
  const rows = await request<RoleOptionDto[]>(`/me/fields/${fieldId}/roles`);
  return rows.map((row) => ({ name: row.name, isCurated: row.is_curated }));
}

export async function getPromptSuggestions(): Promise<string[]> {
  return request("/me/prompt-suggestions");
}

export async function getTopicSuggestions(): Promise<TopicSuggestions> {
  return request("/me/topic-suggestions");
}

export async function getMyProfile(): Promise<Profile> {
  return request("/me/profile");
}

export async function updateMyProfile(update: ProfileUpdate): Promise<Profile> {
  // Only include keys the caller actually set - e.g. InterestsStep saves
  // interest_free_text alone; sending undefined Field/Role keys would falsely
  // resubmit "not provided" as an explicit part of the request.
  const body: Record<string, unknown> = {};
  if (update.fieldName !== undefined) body.field_name = update.fieldName;
  if (update.fieldIsOther !== undefined) body.field_is_other = update.fieldIsOther;
  if (update.roleName !== undefined) body.role_name = update.roleName;
  if (update.roleIsOther !== undefined) body.role_is_other = update.roleIsOther;
  if (update.experienceBucket !== undefined) body.experience_bucket = update.experienceBucket;
  if (update.interestFreeText !== undefined) body.interest_free_text = update.interestFreeText;

  return request("/me/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
