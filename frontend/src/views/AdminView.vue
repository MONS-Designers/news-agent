<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">אישור מקורות</h1>
        <p class="mt-1 text-sm text-neutral-500">
          סקירת מקורות ממתינים - אישור או דחיה.
        </p>
      </div>
      <button
        @click="loadSources"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        טעינת מקורות ממתינים
      </button>
    </div>

    <div
      v-if="actionError"
      class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      {{ actionError }}
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">טוען…</div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

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
          <div class="flex shrink-0 items-center gap-2">
            <span
              class="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
            >
              {{ statusLabel(source.status) }}
            </span>
            <button
              @click="updateStatus(source, 'approved')"
              :disabled="pendingId === source.id"
              class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 disabled:opacity-50"
            >
              אישור
            </button>
            <button
              @click="updateStatus(source, 'rejected')"
              :disabled="pendingId === source.id"
              class="inline-flex items-center justify-center rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-500 disabled:opacity-50"
            >
              דחייה
            </button>
          </div>
        </div>
      </li>
    </ul>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      אין מקורות ממתינים.
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ApiError, listPendingSources, setSourceStatus, type Source } from "@/api/client";

const sources = ref<Source[]>([]);
const loading = ref(false);
const errorMessage = ref("");
const actionError = ref("");
const pendingId = ref<number | null>(null);

const STATUS_LABELS: Record<string, string> = {
  pending: "ממתין",
  approved: "מאושר",
  rejected: "נדחה",
};
function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

async function loadSources() {
  loading.value = true;
  errorMessage.value = "";
  try {
    sources.value = await listPendingSources();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = "יש להתחבר עם Google כדי לצפות במקורות הממתינים.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "לחשבון שלך אין הרשאת מנהל.";
    } else {
      errorMessage.value = "טעינת המקורות נכשלה.";
    }
  } finally {
    loading.value = false;
  }
}

async function updateStatus(source: Source, status: "approved" | "rejected") {
  pendingId.value = source.id;
  actionError.value = "";
  try {
    await setSourceStatus(source.id, status);
    sources.value = sources.value.filter((s) => s.id !== source.id);
  } catch {
    actionError.value = `הפעולה נכשלה: לא ניתן ${status === "approved" ? "לאשר" : "לדחות"} את המקור.`;
  } finally {
    pendingId.value = null;
  }
}

onMounted(loadSources);
</script>
