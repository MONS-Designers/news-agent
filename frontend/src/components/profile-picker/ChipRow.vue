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
        :key="option.id"
        type="button"
        class="chip"
        :class="{ selected: selectedName === option.name && !isOther }"
        :aria-pressed="selectedName === option.name && !isOther"
        @click="selectCurated(option.name)"
      >
        {{ option.name }}
      </button>
      <button
        type="button"
        class="chip chip-other"
        :class="{ selected: isOther }"
        :aria-pressed="isOther"
        @click="selectOther"
      >
        Other
      </button>
    </div>

    <input
      v-if="isOther && !placeholderText"
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
// Server-side bound (services/profile.py MAX_NAME_LENGTH). Mirrored here so the
// input cannot produce a value the save will reject.
const MAX_NAME_LENGTH = 100;

defineProps<{
  stepNum: string;
  label: string;
  options: { id: number; name: string }[];
  otherPlaceholder: string;
  /** When set, the row renders this hint instead of any chips. */
  placeholderText: string | null;
}>();

const selectedName = defineModel<string | null>("selectedName", { required: true });
const isOther = defineModel<boolean>("isOther", { required: true });
const otherText = defineModel<string>("otherText", { required: true });

function selectCurated(name: string) {
  isOther.value = false;
  otherText.value = "";
  selectedName.value = name;
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
