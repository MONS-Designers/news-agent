<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">Taxonomy queue</h1>
        <p class="mt-1 text-sm text-neutral-500">
          Review "Other" field and role submissions from users.
        </p>
      </div>
      <button
        @click="loadSuggestions"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        Load pending suggestions
      </button>
    </div>

    <div
      v-if="actionError"
      class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      {{ actionError }}
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">Loading…</div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

    <ul v-else-if="suggestions.length > 0" class="space-y-3">
      <li
        v-for="suggestion in suggestions"
        :key="suggestion.id"
        class="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <p class="truncate font-medium">{{ suggestion.text }}</p>
            <p class="truncate text-sm text-neutral-500">{{ context(suggestion) }}</p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <span
              class="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"
            >
              {{ suggestion.kind }}
            </span>
            <span class="text-sm text-neutral-500">
              {{ suggestion.submission_count }}
              {{ suggestion.submission_count === 1 ? "submission" : "submissions" }}
            </span>
          </div>
        </div>

        <div class="mt-4 flex flex-col gap-2 border-t border-neutral-100 pt-4 sm:flex-row sm:items-center">
          <label class="sr-only" :for="`name-${suggestion.id}`">Curated name</label>
          <input
            :id="`name-${suggestion.id}`"
            v-model="curatedNames[suggestion.id]"
            :disabled="!canPromote(suggestion)"
            class="min-w-0 flex-1 rounded-lg border border-neutral-300 px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900 disabled:bg-neutral-50 disabled:text-neutral-400"
          />
          <div class="flex shrink-0 items-center gap-2">
            <button
              @click="decide(suggestion, 'approved')"
              :disabled="pendingId === suggestion.id || !canPromote(suggestion)"
              class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 disabled:opacity-50"
            >
              Promote
            </button>
            <button
              @click="decide(suggestion, 'rejected')"
              :disabled="pendingId === suggestion.id"
              class="inline-flex items-center justify-center rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-500 disabled:opacity-50"
            >
              Dismiss
            </button>
          </div>
        </div>

        <p v-if="!canPromote(suggestion)" class="mt-2 text-sm text-neutral-500">
          This role was submitted under a field that is not curated yet. Promote that field first,
          or dismiss this suggestion.
        </p>
      </li>
    </ul>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      No pending taxonomy suggestions.
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import {
  ApiError,
  decideTaxonomySuggestion,
  listPendingTaxonomySuggestions,
  type PendingTaxonomySuggestion,
} from "@/api/client";

const suggestions = ref<PendingTaxonomySuggestion[]>([]);
const curatedNames = ref<Record<number, string>>({});
const loading = ref(false);
const errorMessage = ref("");
const actionError = ref("");
const pendingId = ref<number | null>(null);

// A role submitted under a field that is itself uncurated "Other" text carries
// no field_id, so field_name is null for role rows too — not only field rows.
function isOrphanRole(suggestion: PendingTaxonomySuggestion): boolean {
  return suggestion.kind === "role" && suggestion.field_name === null;
}

function context(suggestion: PendingTaxonomySuggestion): string {
  if (suggestion.kind === "field") {
    return "New field";
  }
  return suggestion.field_name ? `Under ${suggestion.field_name}` : "Field not curated";
}

// Role.field_id is a non-nullable foreign key, so there is no row the backend
// could write for an orphan role — it answers 400. Mirror that in the UI rather
// than offering an action that always fails.
function canPromote(suggestion: PendingTaxonomySuggestion): boolean {
  return !isOrphanRole(suggestion);
}

async function loadSuggestions() {
  loading.value = true;
  errorMessage.value = "";
  try {
    suggestions.value = await listPendingTaxonomySuggestions();
    curatedNames.value = Object.fromEntries(suggestions.value.map((s) => [s.id, s.text]));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = "Sign in with Google to view pending suggestions.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "Your account does not have admin access.";
    } else {
      errorMessage.value = "Failed to load taxonomy suggestions.";
    }
  } finally {
    loading.value = false;
  }
}

async function decide(
  suggestion: PendingTaxonomySuggestion,
  status: "approved" | "rejected",
) {
  pendingId.value = suggestion.id;
  actionError.value = "";
  try {
    const name = status === "approved" ? curatedNames.value[suggestion.id] : undefined;
    await decideTaxonomySuggestion(suggestion.id, status, name);
    suggestions.value = suggestions.value.filter((s) => s.id !== suggestion.id);
  } catch {
    actionError.value = `Failed to ${status === "approved" ? "promote" : "dismiss"} suggestion.`;
  } finally {
    pendingId.value = null;
  }
}

onMounted(loadSuggestions);
</script>
