<template>
  <div>
    <div class="suggestbar">
      <div class="block-head">
        <span class="step-num">3</span>
        <span class="step-label">Suggested topics</span>
      </div>
      <p v-if="!loading && !loadError" class="counter">
        Selected <b>{{ pickedChips.length }}</b> / {{ MAX_TOPICS }}
      </p>
    </div>

    <p v-if="loading" class="placeholder">Finding suggestions for you…</p>
    <p v-else-if="loadError" class="form-error">Couldn't load topics. Try reloading the page.</p>

    <template v-else>
      <div class="topic-grid" role="group" aria-label="Suggested topics">
        <button
          v-for="chip in allChips"
          :key="chipKey(chip)"
          type="button"
          class="topic"
          :class="{ picked: isPicked(chip), faint: !isPicked(chip) }"
          :aria-pressed="isPicked(chip)"
          @click="toggleChip(chip)"
        >
          {{ chip.name }}
          <span v-if="isPicked(chip)" class="x" aria-hidden="true">✕</span>
        </button>
      </div>
      <p class="hint">{{ capHintMessage || "Tap a faint topic to select it." }}</p>
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
import { useRouter } from "vue-router";
import { getTopicSuggestions, listMyPreferences, updateMyPreferences } from "@/api/client";

const router = useRouter();

const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ back: []; saved: [] }>();

// Must match services/preferences.py:MAX_TOPICS.
const MAX_TOPICS = 4;

const POLL_INTERVAL_MS = 400;
// ~45s budget. This story added a second sequential LLM call
// (suggest_new_topics after suggest_topics) to the same background
// computation this polls for — measured ~25s combined against a real
// OpenRouter model, well past the previous single-call ~8s budget. A
// too-short budget doesn't error, it silently falls back to "current
// subscriptions", which looks indistinguishable from the feature not
// working at all.
const MAX_POLL_ATTEMPTS = 112;

const loading = ref(true);
const loadError = ref(false);
const saving = ref(false);
const saveMessage = ref("");

// A suggestion chip is either an existing Topic (real topic_id, shown by its
// stored name) or an LLM-invented not-yet-existing name (no id until saved).
// Picks are tracked as the same tagged union, not a bare number[], since a
// "new" pick has no id to store until Save preferences resolves it.
type SuggestionChip =
  | { kind: "existing"; topicId: number; name: string }
  | { kind: "new"; name: string };
type Pick = { kind: "existing"; topicId: number } | { kind: "new"; name: string };

const allChips = ref<SuggestionChip[]>([]);
const pickedChips = ref<Pick[]>([]);

function chipKey(chip: SuggestionChip | Pick): string {
  return chip.kind === "existing" ? `existing:${chip.topicId}` : `new:${chip.name}`;
}

function toPick(chip: SuggestionChip): Pick {
  return chip.kind === "existing"
    ? { kind: "existing", topicId: chip.topicId }
    : { kind: "new", name: chip.name };
}

function isPicked(chip: SuggestionChip): boolean {
  const key = chipKey(chip);
  return pickedChips.value.some((pick) => chipKey(pick) === key);
}

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
  return {
    suggestion_status: "failed" as const,
    suggested_topic_ids: null,
    suggested_new_topic_names: null,
  };
}

const capHintMessage = ref("");
let capHintTimer: ReturnType<typeof setTimeout> | undefined;

function showCapHint() {
  capHintMessage.value = "Deselect a topic first — you're at 4.";
  clearTimeout(capHintTimer);
  capHintTimer = setTimeout(() => {
    capHintMessage.value = "";
  }, 2500);
}

function toggleChip(chip: SuggestionChip) {
  const key = chipKey(chip);
  if (isPicked(chip)) {
    pickedChips.value = pickedChips.value.filter((pick) => chipKey(pick) !== key);
  } else if (pickedChips.value.length >= MAX_TOPICS) {
    // Never decide for the user which of their 4 to drop — do nothing and
    // tell them why, instead of silently auto-swapping out the oldest pick.
    showCapHint();
  } else {
    pickedChips.value = [...pickedChips.value, toPick(chip)];
  }
}

async function onSave() {
  if (saving.value) return;
  saving.value = true;
  saveMessage.value = "";
  try {
    const topicIds = pickedChips.value
      .filter((pick): pick is { kind: "existing"; topicId: number } => pick.kind === "existing")
      .map((pick) => pick.topicId);
    const newTopicNames = pickedChips.value
      .filter((pick): pick is { kind: "new"; name: string } => pick.kind === "new")
      .map((pick) => pick.name);
    await updateMyPreferences(topicIds, newTopicNames);
    saveMessage.value = "Saved.";
    emit("saved");
    router.push("/");
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
    const topicNames = new Map(allPrefs.map((p) => [p.topic_id, p.name]));

    const suggestedExistingIds = suggestionResult.suggested_topic_ids ?? [];
    const suggestedNewNames = suggestionResult.suggested_new_topic_names ?? [];

    // Built before the ready-check below (not filtered post-hoc) — a
    // suggested id that doesn't resolve locally (e.g. stale by the time this
    // page loads) must not silently pass the non-empty check and then render
    // an empty grid, breaking FR-9's "never risk a dead end" guarantee.
    const existingChips: SuggestionChip[] = suggestedExistingIds
      .filter((id) => topicNames.has(id))
      .map((id) => ({ kind: "existing", topicId: id, name: topicNames.get(id)! }));
    const newChips: SuggestionChip[] = suggestedNewNames.map((name) => ({
      kind: "new",
      name,
    }));
    const readyChips = [...existingChips, ...newChips];

    if (suggestionResult.suggestion_status === "ready" && readyChips.length > 0) {
      allChips.value = readyChips;
      pickedChips.value = allChips.value.slice(0, MAX_TOPICS).map(toPick);
    } else {
      // Failed, or ready-but-empty (shouldn't happen given the popularity
      // fallback ranks every topic, but never risk a dead end — FR-9).
      // Prefer the user's own existing subscriptions over arbitrary topics.
      const subscribed = allPrefs.filter((p) => p.subscribed);
      const rest = allPrefs.filter((p) => !p.subscribed);
      const ordered = [...subscribed, ...rest];
      allChips.value = ordered.map((p) => ({
        kind: "existing" as const,
        topicId: p.topic_id,
        name: p.name,
      }));
      const picked = subscribed.length > 0 ? subscribed : ordered;
      pickedChips.value = picked
        .slice(0, MAX_TOPICS)
        .map((p) => ({ kind: "existing" as const, topicId: p.topic_id }));
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
