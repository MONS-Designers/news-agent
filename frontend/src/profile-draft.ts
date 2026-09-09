// Shared profile/preferences draft store - single source of truth for
// PreferencesView and the profile wizard steps, mirroring frontend/src/auth.ts's
// existing module-level ref + plain functions pattern (no Pinia - none installed).
// PreferencesView seeds it once via initProfileDraft(); AboutYouStep/InterestsStep/
// TopicsStep read it directly for prefill and patch it on save, so siblings see
// each other's changes without ProfilePickerShell relaying anything.
import { ref } from "vue";
import type { Profile, TopicPreference } from "@/api/client";

export const profileDraft = ref<Profile | null>(null);
export const preferencesDraft = ref<TopicPreference[]>([]);

export function initProfileDraft(profile: Profile, preferences: TopicPreference[]): void {
  profileDraft.value = profile;
  preferencesDraft.value = preferences;
}

export function patchProfileDraft(patch: Partial<Profile>): void {
  if (profileDraft.value) {
    Object.assign(profileDraft.value, patch);
  }
}
