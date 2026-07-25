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

    <template v-else>
      <ProfilePickerShell />

      <template v-if="preferences.length > 0">
        <ul class="space-y-3">
          <li
            v-for="pref in preferences"
            :key="pref.topic_id"
            class="flex items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
          >
            <p class="font-medium">{{ pref.name }}</p>
            <label class="inline-flex cursor-pointer items-center gap-2 text-sm text-neutral-600">
              <input
                type="checkbox"
                v-model="pref.subscribed"
                class="size-4 rounded border-neutral-300 text-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
              />
              Subscribed
            </label>
          </li>
        </ul>

        <div class="flex items-center gap-3">
          <button
            @click="savePreferences"
            :disabled="saving"
            class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900 disabled:opacity-50"
          >
            {{ saving ? "Saving…" : "Save" }}
          </button>
          <p v-if="saveMessage" class="text-sm text-neutral-500">{{ saveMessage }}</p>
        </div>
      </template>

      <div
        v-else
        class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
      >
        No topics available.
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ApiError, listMyPreferences, updateMyPreferences, type TopicPreference } from "@/api/client";
import ProfilePickerShell from "@/components/profile-picker/ProfilePickerShell.vue";

const preferences = ref<TopicPreference[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const saveMessage = ref("");

async function loadPreferences() {
  loading.value = true;
  errorMessage.value = "";
  saveMessage.value = "";
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

async function savePreferences() {
  saving.value = true;
  saveMessage.value = "";
  try {
    const topicIds = preferences.value.filter((p) => p.subscribed).map((p) => p.topic_id);
    preferences.value = await updateMyPreferences(topicIds);
    saveMessage.value = "Saved.";
  } catch {
    saveMessage.value = "Failed to save preferences.";
  } finally {
    saving.value = false;
  }
}

onMounted(loadPreferences);
</script>
