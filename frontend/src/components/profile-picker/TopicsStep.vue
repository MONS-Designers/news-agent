<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-2.5">
        <span
          class="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-hd-accent-2/16 text-[11px] font-bold text-hd-accent"
          >3</span
        >
        <span class="text-[11px] font-bold uppercase tracking-[2px] text-hd-label">נושאים מוצעים</span>
      </div>
      <p v-if="!loading && !loadError" class="text-xs text-hd-muted">
        נבחרו <b class="text-hd-accent">{{ pickedChips.length }}</b> מתוך {{ MAX_TOPICS }}
      </p>
    </div>

    <p v-if="loading" class="text-[13px] text-hd-muted" role="status" aria-live="polite">
      {{ extendedWait ? "עדיין מנסים - זה לוקח יותר זמן מהרגיל…" : "מוצא הצעות בשבילך…" }}
    </p>
    <p v-else-if="loadError" class="text-xs text-hd-subtitle">טעינת הנושאים נכשלה. אפשר לרענן את הדף.</p>

    <template v-else>
      <div class="flex flex-wrap gap-2.5" role="group" aria-label="נושאים מוצעים">
        <button
          v-for="chip in allChips"
          :key="chipKey(chip)"
          type="button"
          :class="topicClasses(isPicked(chip))"
          :aria-pressed="isPicked(chip)"
          @click="toggleChip(chip)"
        >
          {{ chip.name }}
          <span v-if="isPicked(chip)" class="ms-1 text-[11px] opacity-60" aria-hidden="true">✕</span>
        </button>
      </div>
      <p class="mt-3.5 text-xs text-hd-muted">{{ capHintMessage || "יש להקיש על נושא דהוי כדי לבחור בו." }}</p>
    </template>

    <div class="mt-7 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3.5">
      <button type="button" :class="BTN_GHOST" :disabled="saving" @click="emit('back')">חזרה →</button>
      <div class="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:gap-3.5">
        <p v-if="saveMessage" class="text-xs text-hd-subtitle">{{ saveMessage }}</p>
        <button type="button" :class="BTN_PRIMARY" :disabled="saving || loading || loadError" @click="onSave">
          {{ saving ? "שומר…" : "אני רוצה לקבל את זה" }}
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
// ~45s budget. The background computation this polls for makes two LLM calls
// (suggest_topics and suggest_new_topics). They now run concurrently (GH #36),
// so the normal wait is the slower of the two - ~14s against a real OpenRouter
// model - but a run that retries a failed call can still outlast this budget.
// A too-short budget doesn't error, it silently falls back to "current
// subscriptions", which looks indistinguishable from the feature not working
// at all.
const MAX_POLL_ATTEMPTS = 112;

const loading = ref(true);
// Set while the backend reports "pending_slow" - one of its two concurrent
// LLM calls failed and it's waiting out the other's retries (GH #36). Only
// swaps the loading copy; polling and the fallback are unchanged.
const extendedWait = ref(false);
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

const TOPIC_BASE =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border px-4 py-[9px] text-[13.5px] [font-family:inherit] motion-reduce:transition-none [transition:border-color_0.18s_ease,background_0.18s_ease,transform_0.18s_ease] active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2";
const TOPIC_PICKED =
  "border-hd-accent-2/50 bg-gradient-to-b from-hd-accent-2/22 to-hd-accent-2/[0.09] text-white";
// Hover gated behind (hover:hover) so a tap doesn't leave a faint pill stuck
// looking hovered on touch devices (see ChipRow.vue's CHIP_UNSELECTED).
const TOPIC_FAINT =
  "border-dashed border-white/[0.09] bg-white/[0.02] text-hd-subtitle opacity-45 [@media(hover:hover)]:hover:border-white/[0.22]";
function topicClasses(picked: boolean): string {
  return `${TOPIC_BASE} ${picked ? TOPIC_PICKED : TOPIC_FAINT}`;
}

const BTN_BASE =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border-0 text-[13.5px] font-semibold [font-family:inherit] [transition:transform_0.18s_ease] motion-reduce:transition-none active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:active:scale-100";
const BTN_PRIMARY = `${BTN_BASE} px-[22px] py-[11px] bg-gradient-to-b from-[#7b86ff] to-[#5c68e8] text-white shadow-[0_10px_24px_-10px_rgba(109,123,255,0.6)] disabled:opacity-35 disabled:shadow-none`;
const BTN_GHOST = `${BTN_BASE} px-2 py-[11px] bg-transparent text-hd-label [@media(hover:hover)]:[&:hover:not(:disabled)]:text-hd-chip disabled:opacity-35`;

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
    extendedWait.value = result.suggestion_status === "pending_slow";
    await sleep(POLL_INTERVAL_MS);
  }
  // Exhausted the polling budget - treat like a failure so the fallback below
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
  capHintMessage.value = "יש לבטל בחירה של נושא קודם - הגעת ל-4.";
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
    // Never decide for the user which of their 4 to drop - do nothing and
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
    saveMessage.value = "נשמר.";
    emit("saved");
    router.push("/");
  } catch {
    saveMessage.value = "שמירת ההעדפות נכשלה.";
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

    // Built before the ready-check below (not filtered post-hoc) - a
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
      // Only pre-select real, admin-curated topics - never an LLM-invented
      // name. An invented topic is created with status='pending' and no RSS
      // sources behind it, so auto-subscribing someone to one silently fills
      // a slot (of only MAX_TOPICS) with a topic that produces zero articles.
      // Invented names stay on screen as unselected chips the user can opt
      // into deliberately.
      pickedChips.value = existingChips.slice(0, MAX_TOPICS).map(toPick);
    } else {
      // Failed, or ready-but-empty (shouldn't happen given the popularity
      // fallback ranks every topic, but never risk a dead end - FR-9).
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
// Back navigation) - so `onMounted` would fire far too early, at page load,
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
