<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">My topic preferences</h1>
        <p class="mt-1 text-sm text-neutral-500">
          Choose which topics appear in your daily digest.
        </p>
      </div>
      <button
        @click="loadPreferences"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        Reload
      </button>
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">Loading…</div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

    <ProfilePickerShell @topics-saved="refreshPreferencesQuietly" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ApiError, listMyPreferences, type TopicPreference } from "@/api/client";
import ProfilePickerShell from "@/components/profile-picker/ProfilePickerShell.vue";

const preferences = ref<TopicPreference[]>([]);
const loading = ref(false);
const errorMessage = ref("");

async function loadPreferences() {
  loading.value = true;
  errorMessage.value = "";
  try {
    preferences.value = await listMyPreferences();
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
