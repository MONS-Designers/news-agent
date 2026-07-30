<template>
  <div>
    <div class="block-head">
      <span class="step-num">2</span>
      <span class="step-label">Interests (optional)</span>
    </div>

    <div v-if="promptSuggestions.length" class="prompt-chips" role="group" aria-label="Example prompts">
      <button
        v-for="(prompt, index) in promptSuggestions"
        :key="`${index}-${prompt}`"
        type="button"
        class="prompt-chip"
        @click="interestFreeText = prompt"
      >
        {{ prompt }}
      </button>
    </div>

    <textarea
      v-model="interestFreeText"
      class="interest-textarea"
      placeholder="Type freely — we'll use this to sharpen your suggestions..."
      rows="4"
      aria-label="Your interests, in your own words"
    ></textarea>

    <div class="nav-row">
      <button type="button" class="btn ghost" :disabled="saving" @click="emit('back')">
        ← Back
      </button>
      <div class="nav-right">
        <p v-if="saveError" class="form-error">{{ saveError }}</p>
        <button type="button" class="btn ghost" :disabled="saving" @click="advance">
          Skip for now →
        </button>
        <button type="button" class="btn primary" :disabled="saving" @click="advance">
          {{ saving ? "Saving…" : "Continue" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref } from "vue";
import { getPromptSuggestions, updateMyProfile } from "@/api/client";

const props = defineProps<{ active: boolean }>();
const emit = defineEmits<{ continue: []; back: [] }>();

const interestFreeText = ref("");
const saving = ref(false);
const saveError = ref("");
const promptSuggestions = ref<string[]>([]);

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
 * FR-4). Both save whatever text exists (nothing to save if blank, so no API
 * call is made) and advance; they only differ in label. */
async function advance() {
  if (saving.value) return;
  const text = interestFreeText.value.trim();
  if (!text) {
    emit("continue");
    return;
  }

  saving.value = true;
  saveError.value = "";
  try {
    await updateMyProfile({ interestFreeText: text });
    emit("continue");
  } catch {
    saveError.value = "Couldn't save. Check your connection and try again.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
/* Mirrors ChipRow.vue's .block-head/.step-num/.step-label — scoped styles
   don't cross components, so this is intentionally duplicated. */
.block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 16px;
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

.prompt-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.prompt-chip {
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.02);
  color: #8b93a7;
  font-size: 12.5px;
  cursor: pointer;
  font-family: inherit;
}
.prompt-chip:hover {
  border-color: rgba(255, 255, 255, 0.22);
  color: #c4cadb;
}
.prompt-chip:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}

.interest-textarea {
  width: 100%;
  min-height: 110px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.02);
  color: #eef1f8;
  font-size: 13.5px;
  font-family: inherit;
  line-height: 1.55;
  resize: vertical;
}
.interest-textarea:focus-visible {
  outline: none;
  border-color: rgba(109, 123, 255, 0.35);
}
.interest-textarea::placeholder {
  color: #565f74;
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

.form-error {
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
</style>
