<template>
  <div>
    <div class="suggestbar">
      <div class="block-head">
        <span class="step-num">3</span>
        <span class="step-label">Suggested topics</span>
      </div>
      <p v-if="!loading && !loadError" class="counter">
        Selected <b>{{ pickedIds.length }}</b> / {{ MAX_TOPICS }}
      </p>
    </div>

    <p v-if="loading" class="placeholder">Finding suggestions for you…</p>
    <p v-else-if="loadError" class="form-error">Couldn't load topics. Try reloading the page.</p>

    <template v-else>
      <div class="topic-grid" role="group" aria-label="Suggested topics">
        <button
          v-for="id in allTopicIds"
          :key="id"
          type="button"
          class="topic"
          :class="{ picked: pickedIds.includes(id), faint: !pickedIds.includes(id) }"
          :aria-pressed="pickedIds.includes(id)"
          @click="toggleTopic(id)"
        >
          {{ topicNames.get(id) ?? `Topic ${id}` }}
          <span v-if="pickedIds.includes(id)" class="x" aria-hidden="true">✕</span>
        </button>
      </div>
      <p class="hint">Tap a faint topic to swap it in for one of your 4.</p>
    </template>

    <div class="nav-row">
      <button type="button" class="btn ghost" :disabled="saving" @click="emit('back')">
        ← Back
      </button>
      <div class="nav-right">
        <p v-if="saveMessage" class="save-message">{{ saveMessage }}</p>
        <button
          type="button"
          class="btn primary"
          :disabled="saving || loading || loadError"
          @click="onSave"
        >
          {{ saving ? "Saving…" : "Save preferences" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { getTopicSuggestions, listMyPreferences, updateMyPreferences } from "@/api/client";

const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ back: []; saved: [] }>();

// Must match services/preferences.py:MAX_TOPICS.
const MAX_TOPICS = 4;

const POLL_INTERVAL_MS = 400;
const MAX_POLL_ATTEMPTS = 20; // ~8s budget for a "brief loading state"

const loading = ref(true);
const loadError = ref(false);
const saving = ref(false);
const saveMessage = ref("");

const allTopicIds = ref<number[]>([]);
const pickedIds = ref<number[]>([]);
const topicNames = ref<Map<number, string>>(new Map());

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollForSuggestions() {
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
    const result = await getTopicSuggestions();
    if (result.suggestion_status === "ready" || result.suggestion_status === "failed") {
      return result;
    }
    await sleep(POLL_INTERVAL_MS);
  }
  // Exhausted the polling budget — treat like a failure so the fallback below
  // still produces a non-empty pick (FR-9), never an infinite loading state.
  return { suggestion_status: "failed" as const, suggested_topic_ids: null };
}

function toggleTopic(id: number) {
  if (pickedIds.value.includes(id)) {
    pickedIds.value = pickedIds.value.filter((x) => x !== id);
  } else if (pickedIds.value.length >= MAX_TOPICS) {
    // FIFO swap: drop the oldest pick, add the newly-tapped one — keeps the
    // total at exactly 4, matching "swaps it in for one of the 4."
    pickedIds.value = [...pickedIds.value.slice(1), id];
  } else {
    pickedIds.value = [...pickedIds.value, id];
  }
}

async function onSave() {
  if (saving.value) return;
  saving.value = true;
  saveMessage.value = "";
  try {
    await updateMyPreferences(pickedIds.value);
    saveMessage.value = "Saved.";
    emit("saved");
  } catch {
    saveMessage.value = "Failed to save preferences.";
  } finally {
    saving.value = false;
  }
}

async function load() {
  try {
    const [suggestionResult, allPrefs] = await Promise.all([
      pollForSuggestions(),
      listMyPreferences(),
    ]);
    topicNames.value = new Map(allPrefs.map((p) => [p.topic_id, p.name]));

    if (
      suggestionResult.suggestion_status === "ready" &&
      suggestionResult.suggested_topic_ids &&
      suggestionResult.suggested_topic_ids.length > 0
    ) {
      allTopicIds.value = suggestionResult.suggested_topic_ids;
      pickedIds.value = allTopicIds.value.slice(0, MAX_TOPICS);
    } else {
      // Failed, or ready-but-empty (shouldn't happen given the popularity
      // fallback ranks every topic, but never risk a dead end — FR-9).
      // Prefer the user's own existing subscriptions over arbitrary topics.
      const subscribed = allPrefs.filter((p) => p.subscribed).map((p) => p.topic_id);
      const rest = allPrefs.map((p) => p.topic_id).filter((id) => !subscribed.includes(id));
      allTopicIds.value = [...subscribed, ...rest];
      pickedIds.value = (subscribed.length > 0 ? subscribed : allTopicIds.value).slice(
        0,
        MAX_TOPICS,
      );
    }
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

// This component is kept mounted via ProfilePickerShell's v-show even when
// Step 3 isn't visible yet (same pattern as Steps 1-2, so state survives
// Back navigation) — so `onMounted` would fire far too early, at page load,
// capturing stale suggestion data from a previous session instead of the
// fresh one this flow's own save just produced. Load only once, the first
// time this step actually becomes active.
let hasLoaded = false;
watch(
  () => props.active,
  (active) => {
    if (active && !hasLoaded) {
      hasLoaded = true;
      load();
    }
  },
  { immediate: true },
);
</script>

<style scoped>
.block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
}
.step-num {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: rgba(109, 123, 255, 0.16);
  color: #a9b1ff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #6b7288;
}

.suggestbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.counter {
  font-size: 12px;
  color: #565f74;
  margin: 0;
}
.counter b {
  color: #a9b1ff;
}

.placeholder {
  color: #565f74;
  font-size: 13px;
  margin: 0;
}
.form-error {
  color: #8b93a7;
  font-size: 12px;
  margin: 0;
}

.topic-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.topic {
  padding: 9px 16px;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.02);
  color: #8b93a7;
  font-size: 13.5px;
  cursor: pointer;
  font-family: inherit;
  transition:
    border-color 0.18s ease,
    background 0.18s ease;
}
.topic:hover {
  border-color: rgba(255, 255, 255, 0.22);
}
.topic:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
.topic.picked {
  background: linear-gradient(180deg, rgba(109, 123, 255, 0.22), rgba(109, 123, 255, 0.09));
  border-color: rgba(109, 123, 255, 0.5);
  color: #fff;
}
.topic.faint {
  opacity: 0.45;
  border-style: dashed;
}
.topic .x {
  opacity: 0.6;
  font-size: 11px;
  margin-left: 4px;
}

.hint {
  font-size: 12px;
  color: #565f74;
  margin: 14px 0 0;
}

.nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 28px;
}
.nav-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.save-message {
  color: #8b93a7;
  font-size: 12px;
  margin: 0;
}

.btn {
  padding: 11px 22px;
  border-radius: 10px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font-family: inherit;
}
.btn:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
.btn:disabled {
  cursor: not-allowed;
}
.btn.primary {
  background: linear-gradient(180deg, #7b86ff, #5c68e8);
  color: #fff;
  box-shadow: 0 10px 24px -10px rgba(109, 123, 255, 0.6);
}
.btn.primary:disabled {
  opacity: 0.35;
  box-shadow: none;
}
.btn.ghost {
  padding: 11px 8px;
  background: transparent;
  color: #6b7288;
}
.btn.ghost:hover:not(:disabled) {
  color: #c4cadb;
}
.btn.ghost:disabled {
  opacity: 0.35;
}

@media (prefers-reduced-motion: reduce) {
  .topic {
    transition: none;
  }
}
</style>
