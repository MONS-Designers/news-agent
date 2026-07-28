<template>
  <div>
    <div class="block-head">
      <span class="step-num">{{ stepNum }}</span>
      <span class="step-label">{{ label }}</span>
    </div>

    <p v-if="placeholderText" class="row-placeholder">{{ placeholderText }}</p>

    <div v-else class="chip-row" role="group" :aria-label="label">
      <button
        v-for="option in options"
        :key="option.id ?? option.name"
        type="button"
        class="chip"
        :class="{ selected: isChipSelected(option) }"
        :aria-pressed="isChipSelected(option)"
        @click="selectChip(option)"
      >
        {{ option.name }}
      </button>
      <button
        type="button"
        class="chip chip-other"
        :class="{ selected: otherButtonActive }"
        :aria-pressed="otherButtonActive"
        @click="selectOther"
      >
        Other
      </button>
    </div>

    <input
      v-if="otherButtonActive && !placeholderText"
      v-model="otherText"
      type="text"
      class="other-input"
      :maxlength="MAX_NAME_LENGTH"
      :placeholder="otherPlaceholder"
      :aria-label="`Your ${label.toLowerCase()}, if not listed above`"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

// Server-side bound (services/profile.py MAX_NAME_LENGTH). Mirrored here so the
// input cannot produce a value the save will reject.
const MAX_NAME_LENGTH = 100;

type Option = { id?: number | null; name: string; isCurated?: boolean };

defineProps<{
  stepNum: string;
  label: string;
  options: Option[];
  otherPlaceholder: string;
  /** When set, the row renders this hint instead of any chips. */
  placeholderText: string | null;
}>();

const selectedName = defineModel<string | null>("selectedName", { required: true });
const isOther = defineModel<boolean>("isOther", { required: true });
const otherText = defineModel<string>("otherText", { required: true });

// True only when `isOther` is set by the real "Other" free-text button, not
// by a not-yet-curated chip (selectNew also sets isOther=true, but keeps
// selectedName pointed at the chip's name — selectOther clears it to null).
// Derived, not local state: a parent resetting isOther/selectedName directly
// (e.g. AboutYouStep.vue clearing the Role row on Field change) must not
// leave this stale, since nothing else here would resync it.
const otherButtonActive = computed(() => isOther.value && selectedName.value === null);

function isChipSelected(option: Option): boolean {
  if (option.isCurated ?? true) {
    return selectedName.value === option.name && !isOther.value;
  }
  return selectedName.value === option.name;
}

function selectChip(option: Option) {
  if (option.isCurated ?? true) {
    selectCurated(option.name);
  } else {
    selectNew(option.name);
  }
}

function selectCurated(name: string) {
  isOther.value = false;
  otherText.value = "";
  selectedName.value = name;
}

/** A not-yet-curated chip: saved exactly like typed "Other" text (same
 * isOther/otherText model values), but rendered as a selected chip. */
function selectNew(name: string) {
  otherText.value = name;
  selectedName.value = name;
  isOther.value = true;
}

function selectOther() {
  // Clear any stale text from a previous visit to "Other" — otherwise
  // switching curated -> Other silently resubmits the old value.
  otherText.value = "";
  selectedName.value = null;
  isOther.value = true;
}
</script>

<style scoped>
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

.row-placeholder {
  font-size: 13.5px;
  color: #565f74;
  margin: 0;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.chip {
  padding: 11px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.02);
  color: #c4cadb;
  font-size: 13.5px;
  cursor: pointer;
  font-family: inherit;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    transform 0.18s ease;
}
.chip:hover {
  border-color: rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.05);
  transform: translateY(-1px);
}
.chip:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
.chip.selected {
  background: linear-gradient(180deg, rgba(109, 123, 255, 0.22), rgba(109, 123, 255, 0.1));
  border-color: rgba(109, 123, 255, 0.55);
  color: #fff;
  box-shadow:
    0 0 0 1px rgba(109, 123, 255, 0.25),
    0 8px 24px -8px rgba(109, 123, 255, 0.45);
}
.chip-other {
  border-style: dashed;
  color: #8b93a7;
}
.chip-other.selected {
  border-style: solid;
}

.other-input {
  margin-top: 12px;
  width: 100%;
  padding: 11px 14px;
  border-radius: 10px;
  border: 1px solid rgba(109, 123, 255, 0.4);
  background: rgba(109, 123, 255, 0.06);
  color: #eef1f8;
  font-size: 13.5px;
  font-family: inherit;
}
.other-input:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
.other-input::placeholder {
  color: #565f74;
}

@media (prefers-reduced-motion: reduce) {
  .chip {
    transition: none;
  }
  .chip:hover {
    transform: none;
  }
}
</style>
