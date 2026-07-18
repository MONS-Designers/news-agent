<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">Source approval</h1>
        <p class="mt-1 text-sm text-neutral-500">
          Review pending sources and approve or reject them.
        </p>
      </div>
      <button
        @click="loadSources"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        Load pending sources
      </button>
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">Loading…</div>

    <ul v-else-if="sources.length > 0" class="space-y-3">
      <li
        v-for="source in sources"
        :key="source.id"
        class="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
      >
        <div class="flex items-center justify-between gap-4">
          <div class="min-w-0">
            <p class="truncate font-medium">{{ source.name }}</p>
            <p class="truncate text-sm text-neutral-500">{{ source.url }}</p>
          </div>
          <span
            class="shrink-0 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
          >
            {{ source.status }}
          </span>
        </div>
      </li>
    </ul>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      No pending sources.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { listPendingSources, type Source } from "@/api/client";

const sources = ref<Source[]>([]);
const loading = ref(false);

async function loadSources() {
  loading.value = true;
  try {
    sources.value = await listPendingSources();
  } catch (error) {
    console.error("Failed to load sources:", error);
  } finally {
    loading.value = false;
  }
}
</script>
