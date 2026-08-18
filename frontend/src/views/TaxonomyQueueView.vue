<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">תור טקסונומיה</h1>
        <p class="mt-1 text-sm text-neutral-500">
          סקירת הצעות תחום ותפקיד מסוג "אחר" שהוגשו על ידי משתמשים.
        </p>
      </div>
      <button
        @click="loadSuggestions"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        טעינת הצעות ממתינות
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

    <div v-else-if="groups.length > 0" class="space-y-8">
      <section v-for="group in groups" :key="group.key">
        <h2 class="mb-3 flex items-center gap-2 text-sm font-semibold text-neutral-700">
          {{ group.title }}
          <span
            v-if="group.blocked"
            class="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"
          >
            ממתין לתחום
          </span>
        </h2>
        <p v-if="group.blocked" class="mb-3 -mt-2 text-sm text-neutral-500">
          התחום שהתפקידים האלה הוגשו תחתיו טרם אושר. אשר קודם את התחום המתאים בקבוצת
          "תחומים חדשים" למעלה, ואז חזור לקדם אותם - או דחה אותם ישירות.
        </p>
        <ul class="space-y-3" :class="{ 'border-s-2 border-neutral-200 ps-4': !group.blocked && group.key !== '__fields' }">
          <li
            v-for="suggestion in group.items"
            :key="suggestion.id"
            class="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div class="min-w-0">
                <p class="truncate font-medium">{{ suggestion.text }}</p>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <span
                  class="rounded-full px-2.5 py-0.5 text-xs font-medium"
                  :class="
                    suggestion.kind === 'field'
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'bg-slate-100 text-slate-700'
                  "
                >
                  {{ kindLabel(suggestion.kind) }}
                </span>
                <span class="text-sm text-neutral-500">
                  {{ suggestion.submission_count === 1 ? "הגשה אחת" : `${suggestion.submission_count} הגשות` }}
                </span>
              </div>
            </div>

            <div class="mt-4 flex flex-col gap-2 border-t border-neutral-100 pt-4 sm:flex-row sm:items-center">
              <label class="sr-only" :for="`name-${suggestion.id}`">שם מתויג</label>
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
                  קדם
                </button>
                <button
                  @click="decide(suggestion, 'rejected')"
                  :disabled="pendingId === suggestion.id"
                  class="inline-flex items-center justify-center rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-red-500 disabled:opacity-50"
                >
                  דחה
                </button>
              </div>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      אין הצעות טקסונומיה ממתינות.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
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
// no field_id, so field_name is null for role rows too - not only field rows.
function isOrphanRole(suggestion: PendingTaxonomySuggestion): boolean {
  return suggestion.kind === "role" && suggestion.field_name === null;
}

const KIND_LABELS: Record<string, string> = {
  field: "תחום",
  role: "תפקיד",
};
function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

interface SuggestionGroup {
  key: string;
  title: string;
  items: PendingTaxonomySuggestion[];
  blocked?: boolean;
}

// Roles are grouped under the curated Field they were submitted under, so the
// hierarchy is visible at a glance instead of living only in a line of body
// text (GH admin feedback: everything looked like "the same kind of thing").
// An orphan role (isOrphanRole) has no field_id to group by - Field.id is
// only ever attached once the Field itself is curated (services/profile.py) -
// so those land in one dedicated "blocked" bucket instead of being scattered,
// unlabeled, among the promotable rows.
const groups = computed<SuggestionGroup[]>(() => {
  const fields = suggestions.value.filter((s) => s.kind === "field");
  const rolesByField = new Map<string, PendingTaxonomySuggestion[]>();
  const blockedRoles: PendingTaxonomySuggestion[] = [];

  for (const suggestion of suggestions.value) {
    if (suggestion.kind !== "role") continue;
    if (suggestion.field_name === null) {
      blockedRoles.push(suggestion);
      continue;
    }
    const list = rolesByField.get(suggestion.field_name) ?? [];
    list.push(suggestion);
    rolesByField.set(suggestion.field_name, list);
  }

  const result: SuggestionGroup[] = [];
  if (fields.length > 0) {
    result.push({ key: "__fields", title: "תחומים חדשים", items: fields });
  }
  for (const [fieldName, items] of rolesByField) {
    result.push({ key: `field:${fieldName}`, title: `תפקידים תחת "${fieldName}"`, items });
  }
  if (blockedRoles.length > 0) {
    result.push({
      key: "__blocked",
      title: "תפקידים שהתחום שלהם עדיין לא אושר",
      items: blockedRoles,
      blocked: true,
    });
  }
  return result;
});

// Role.field_id is a non-nullable foreign key, so there is no row the backend
// could write for an orphan role - it answers 400. Mirror that in the UI rather
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
      errorMessage.value = "התחבר עם Google כדי לצפות בהצעות הממתינות.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "לחשבון שלך אין הרשאת מנהל.";
    } else {
      errorMessage.value = "טעינת הצעות הטקסונומיה נכשלה.";
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
    // A full reload, not a local filter of just this row: approving a Field
    // can unblock a linked Role (its field_id gets backfilled server-side),
    // and rejecting one cascades to reject its linked Roles - both invisible
    // to the client unless the list is re-fetched.
    await loadSuggestions();
  } catch {
    actionError.value = `הפעולה נכשלה: לא ניתן ${status === "approved" ? "לקדם" : "לדחות"} את ההצעה.`;
  } finally {
    pendingId.value = null;
  }
}

onMounted(loadSuggestions);
</script>
