<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">My topic preferences</h1>
      <p class="mt-1 text-sm text-neutral-500">
        Choose which topics appear in your weekly digest.
      </p>
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">Loading…</div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

    <div v-else-if="showSummary" class="space-y-5 rounded-xl border border-neutral-200 p-5">
      <dl class="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
        <div>
          <dt class="text-neutral-500">Field</dt>
          <dd class="font-medium">{{ profile?.field_name }}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Role</dt>
          <dd class="font-medium">{{ profile?.role_name }}</dd>
        </div>
        <div>
          <dt class="text-neutral-500">Experience</dt>
          <dd class="font-medium">{{ experienceLabel }}</dd>
        </div>
        <div v-if="profile?.interest_free_text" class="col-span-2">
          <dt class="text-neutral-500">Interests</dt>
          <dd class="font-medium">{{ profile.interest_free_text }}</dd>
        </div>
      </dl>

      <div>
        <p class="mb-1.5 text-sm text-neutral-500">Subscribed topics</p>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="topic in subscribedTopics"
            :key="topic.topic_id"
            class="rounded-full bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-700"
          >
            {{ topic.name }}
          </span>
          <span v-if="subscribedTopics.length === 0" class="text-xs text-neutral-400">None yet</span>
        </div>
      </div>

      <button
        type="button"
        class="rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        @click="editing = true"
      >
        Edit profile
      </button>
    </div>

    <ProfilePickerShell v-else @topics-saved="refreshPreferencesQuietly" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ApiError, getMyProfile, listMyPreferences, type Profile, type TopicPreference } from "@/api/client";
import ProfilePickerShell from "@/components/profile-picker/ProfilePickerShell.vue";

const preferences = ref<TopicPreference[]>([]);
const profile = ref<Profile | null>(null);
const loading = ref(false);
const errorMessage = ref("");

// A returning user with a completed profile sees a read-only summary first,
// not the wizard — editing (and the suggestion-recompute logic it can
// trigger) only happens when they explicitly choose to.
const editing = ref(false);
const showSummary = computed(() => !editing.value && !!profile.value?.field_name);

// Mirrors AboutYouStep.vue's EXPERIENCE_BUCKETS display labels.
const EXPERIENCE_LABELS: Record<string, string> = {
  "0-2": "0–2 yrs",
  "3-5": "3–5 yrs",
  "6-10": "6–10 yrs",
  "10+": "10+ yrs",
};
const experienceLabel = computed(() => {
  const bucket = profile.value?.experience_bucket;
  return bucket ? (EXPERIENCE_LABELS[bucket] ?? bucket) : "—";
});

const subscribedTopics = computed(() => preferences.value.filter((topic) => topic.subscribed));

async function loadPreferences() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [prefs, prof] = await Promise.all([listMyPreferences(), getMyProfile()]);
    preferences.value = prefs;
    profile.value = prof;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = "Sign in with Google to view your preferences.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "This account has no user profile. Contact an admin.";
    } else {
      errorMessage.value = "Failed to load preferences.";
    }
  } finally {
    loading.value = false;
  }
}

async function refreshPreferencesQuietly() {
  // Unlike loadPreferences, does not touch `loading` — that flag gates
  // ProfilePickerShell behind v-if, so toggling it here would destroy and
  // recreate the whole guided flow (resetting it to Step 1) right after the
  // user just finished it. This just re-syncs the preferences ref.
  try {
    preferences.value = await listMyPreferences();
  } catch {
    // Best-effort background refresh — the guided flow's own save already
    // succeeded and showed its own feedback; a failed refresh here shouldn't
    // interrupt anything.
  }
}

onMounted(loadPreferences);
</script>
