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
        Load preferences
      </button>
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">Loading…</div>

    <ul v-else-if="preferences.length > 0" class="space-y-3">
      <li
        v-for="pref in preferences"
        :key="pref.id"
        class="flex items-center justify-between gap-4 rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
      >
        <p class="font-medium">Topic ID: {{ pref.topic_id }}</p>
        <button
          @click="unsubscribe(pref.id)"
          class="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
        >
          Unsubscribe
        </button>
      </li>
    </ul>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      No topic preferences set.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { listMyPreferences, type TopicPreference } from "@/api/client";

const preferences = ref<TopicPreference[]>([]);
const loading = ref(false);

async function loadPreferences() {
  loading.value = true;
  try {
    preferences.value = await listMyPreferences();
  } catch (error) {
    console.error("Failed to load preferences:", error);
  } finally {
    loading.value = false;
  }
}

function unsubscribe(id: number) {
  preferences.value = preferences.value.filter((p) => p.id !== id);
}
</script>
