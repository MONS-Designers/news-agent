<template>
  <div>
    <div class="mb-4 flex items-center gap-2.5">
      <span
        class="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-hd-accent-2/16 text-[11px] font-bold text-hd-accent"
        >2</span
      >
      <span class="text-[11px] font-bold uppercase tracking-[2px] text-hd-label">Interests (optional)</span>
    </div>

    <div
      v-if="promptSuggestions.length"
      class="mb-3 flex flex-wrap gap-2"
      role="group"
      aria-label="Example prompts"
    >
      <button
        v-for="(prompt, index) in promptSuggestions"
        :key="`${index}-${prompt}`"
        type="button"
        class="inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-full border border-white/[0.09] bg-white/[0.02] px-3 py-[7px] text-[12.5px] text-hd-subtitle [font-family:inherit] [transition:border-color_0.18s_ease,color_0.18s_ease,transform_0.18s_ease] motion-reduce:transition-none [@media(hover:hover)]:hover:border-white/[0.22] [@media(hover:hover)]:hover:text-hd-chip active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2"
        @click="interestFreeText = prompt"
      >
        {{ prompt }}
      </button>
    </div>

    <textarea
      v-model="interestFreeText"
      class="min-h-[110px] w-full resize-y rounded-xl border border-white/[0.09] bg-white/[0.02] p-3.5 text-[13.5px] leading-[1.55] text-hd-fg [font-family:inherit] placeholder:text-hd-muted focus-visible:border-hd-accent-2/35 focus-visible:outline-none"
      placeholder="Type freely — we'll use this to sharpen your suggestions..."
      rows="4"
      aria-label="Your interests, in your own words"
    ></textarea>

    <div class="mt-7 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-3.5">
      <button type="button" :class="BTN_GHOST" :disabled="saving" @click="emit('back')">← Back</button>
      <div class="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:gap-3.5">
        <p v-if="saveError" class="text-xs text-hd-subtitle">{{ saveError }}</p>
        <button type="button" :class="BTN_GHOST" :disabled="saving" @click="advance">Skip for now →</button>
        <button type="button" :class="BTN_PRIMARY" :disabled="saving" @click="advance">
          {{ saving ? "Saving…" : "Continue" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref, onMounted } from "vue";
import { getMyProfile, getPromptSuggestions, updateMyProfile } from "@/api/client";

const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ continue: []; back: [] }>();

const interestFreeText = ref("");
const saving = ref(false);
const saveError = ref("");
const promptSuggestions = ref<string[]>([]);

const BTN_BASE =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border-0 text-[13.5px] font-semibold [font-family:inherit] [transition:transform_0.18s_ease] motion-reduce:transition-none active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:active:scale-100";
const BTN_PRIMARY = `${BTN_BASE} px-[22px] py-[11px] bg-gradient-to-b from-[#7b86ff] to-[#5c68e8] text-white shadow-[0_10px_24px_-10px_rgba(109,123,255,0.6)] disabled:opacity-35 disabled:shadow-none`;
const BTN_GHOST = `${BTN_BASE} px-2 py-[11px] bg-transparent text-hd-label [@media(hover:hover)]:[&:hover:not(:disabled)]:text-hd-chip disabled:opacity-35`;

let initialText = "";

onMounted(async () => {
  try {
    const profile = await getMyProfile();
    interestFreeText.value = profile.interest_free_text ?? "";
    initialText = interestFreeText.value;
  } catch {
    // Best-effort pre-fill only — a failure here just means the textarea
    // starts blank, same as today's behavior, not a blocking error.
  }
});

// Illustrative only (FR-5) — clicking one just fills the textarea, still
// freely editable; a fetch failure just means no hints show, same as the
// pre-LLM behavior, so there's no error branch here. Prompts are fetched
// based on the user's saved profile from Step 1, so wait until this step
// is active (meaning Step 1 has been saved) before fetching.
watch(
  () => props.active,
  async (newActive: boolean) => {
    if (!newActive) return;
    try {
      promptSuggestions.value = (await getPromptSuggestions()).slice(0, 3);
    } catch {
      promptSuggestions.value = [];
    }
  }
);

/** Continue and Skip do the same thing here — Step 2 is never gated (PRD
 * FR-4). Both save whatever text exists (nothing to save if blank or
 * unchanged since load, so no API call — and no suggestion recompute — is
 * made in those cases) and advance; they only differ in label. */
async function advance() {
  if (saving.value) return;
  const text = interestFreeText.value.trim();
  if (!text || text === initialText) {
    emit("continue");
    return;
  }

  saving.value = true;
  saveError.value = "";
  try {
    await updateMyProfile({ interestFreeText: text });
    initialText = text;
    emit("continue");
  } catch {
    saveError.value = "Couldn't save. Check your connection and try again.";
  } finally {
    saving.value = false;
  }
}
</script>
