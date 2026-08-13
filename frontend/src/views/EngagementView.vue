<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">מעורבות בדייג'סט</h1>
        <p class="mt-1 text-sm text-neutral-500">
          פתיחות וקליקים על לינקים בדייג'סטים שנשלחו.
        </p>
      </div>
      <button
        @click="loadEngagement"
        class="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-neutral-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-900"
      >
        רענן
      </button>
    </div>

    <div v-if="loading" class="text-sm text-neutral-500">טוען…</div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

    <ul v-else-if="rows.length > 0" class="space-y-3">
      <li
        v-for="row in rows"
        :key="row.digest_id"
        class="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <p class="truncate font-medium">{{ row.user_email }}</p>
            <p class="truncate text-sm text-neutral-500">{{ row.date }}</p>
          </div>
          <div class="flex shrink-0 flex-wrap items-center gap-2">
            <span
              class="rounded-full px-2.5 py-0.5 text-xs font-medium"
              :class="row.opened_at ? 'bg-emerald-50 text-emerald-700' : 'bg-neutral-100 text-neutral-600'"
            >
              {{ row.opened_at ? "נפתח" : "לא נפתח" }}
            </span>
            <span class="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-600">
              {{ row.articles_clicked }} מתוך {{ row.articles_total }} מאמרים נלחצו
            </span>
            <span
              class="rounded-full px-2.5 py-0.5 text-xs font-medium"
              :class="row.preferences_clicked ? 'bg-emerald-50 text-emerald-700' : 'bg-neutral-100 text-neutral-600'"
            >
              {{ row.preferences_clicked ? "העדפות נלחצו" : "העדפות לא נלחצו" }}
            </span>
          </div>
        </div>

        <p v-if="row.clicked_article_titles.length > 0" class="mt-3 text-sm text-neutral-500">
          נלחצו: {{ row.clicked_article_titles.join(", ") }}
        </p>
      </li>
    </ul>

    <div
      v-else
      class="rounded-xl border border-dashed border-neutral-300 bg-white p-8 text-center text-sm text-neutral-500"
    >
      עדיין לא נשלחו דייג'סטים.
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ApiError, listDigestEngagement, type DigestEngagement } from "@/api/client";

const rows = ref<DigestEngagement[]>([]);
const loading = ref(false);
const errorMessage = ref("");

async function loadEngagement() {
  loading.value = true;
  errorMessage.value = "";
  try {
    rows.value = await listDigestEngagement();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = "התחבר עם Google כדי לצפות במעורבות בדייג'סט.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "לחשבון שלך אין הרשאת מנהל.";
    } else {
      errorMessage.value = "טעינת נתוני המעורבות נכשלה.";
    }
  } finally {
    loading.value = false;
  }
}

onMounted(loadEngagement);
</script>
