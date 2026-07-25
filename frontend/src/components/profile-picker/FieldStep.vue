<template>
  <div>
    <div class="block-head">
      <span class="step-num">1</span>
      <span class="step-label">Field</span>
    </div>

    <div class="chip-row" role="group" aria-label="Field">
      <button
        v-for="field in fields"
        :key="field.id"
        type="button"
        class="chip"
        :class="{ selected: selectedName === field.name && !isOther }"
        :aria-pressed="selectedName === field.name && !isOther"
        @click="selectCurated(field.name)"
      >
        {{ field.name }}
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
      v-if="isOther"
      v-model="otherText"
      type="text"
      class="other-input"
      placeholder="e.g. Marine Biology"
      aria-label="Your field, if not listed above"
    />

    <p v-if="loadError" class="load-error">Couldn't load Field options. Try reloading the page.</p>

    <div class="nav-row">
      <button
        type="button"
        class="btn primary"
        :class="{ disabled: !canContinue }"
        :aria-disabled="!canContinue"
        @click="onContinue"
      >
        Continue
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { listFields, updateMyProfile, type FieldOption } from "@/api/client";

const emit = defineEmits<{ continue: [] }>();

const fields = ref<FieldOption[]>([]);
const selectedName = ref<string | null>(null);
const isOther = ref(false);
const otherText = ref("");
const saving = ref(false);
const loadError = ref(false);

const canContinue = computed(() => {
  if (isOther.value) return otherText.value.trim().length > 0;
  return selectedName.value !== null;
});

function selectCurated(name: string) {
  isOther.value = false;
  selectedName.value = name;
}

function selectOther() {
  isOther.value = true;
}

async function onContinue() {
  if (!canContinue.value || saving.value) return;
  saving.value = true;
  try {
    const fieldName = isOther.value ? otherText.value.trim() : (selectedName.value as string);
    await updateMyProfile(fieldName, isOther.value);
    emit("continue");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    fields.value = await listFields();
  } catch {
    loadError.value = true;
  }
});
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
  outline: none;
  font-family: inherit;
}
.other-input::placeholder {
  color: #565f74;
}

.load-error {
  color: #e5555f;
  font-size: 12px;
  margin: 12px 0 0;
}

.nav-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 28px;
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
.btn.primary {
  background: linear-gradient(180deg, #7b86ff, #5c68e8);
  color: #fff;
  box-shadow: 0 10px 24px -10px rgba(109, 123, 255, 0.6);
}
.btn.primary.disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
  pointer-events: none;
}
</style>
