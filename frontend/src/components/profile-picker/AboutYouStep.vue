<template>
  <div>
    <ChipRow
      step-num="1"
      label="Field"
      :options="fields"
      other-placeholder="e.g. Marine Biology"
      :placeholder-text="null"
      v-model:selected-name="fieldName"
      v-model:is-other="fieldIsOther"
      v-model:other-text="fieldOtherText"
    />

    <div class="row-gap">
      <ChipRow
        step-num="2"
        label="Role"
        :options="roles"
        other-placeholder="e.g. Developer Relations"
        :placeholder-text="rolePlaceholder"
        v-model:selected-name="roleName"
        v-model:is-other="roleIsOther"
        v-model:other-text="roleOtherText"
      />
    </div>

    <fieldset class="row-gap exp-fieldset">
      <legend class="block-head">
        <span class="step-num">3</span>
        <span class="step-label">Experience</span>
      </legend>
      <div class="seg-row">
        <label
          v-for="bucket in EXPERIENCE_BUCKETS"
          :key="bucket.value"
          class="seg"
          :class="{ selected: experienceBucket === bucket.value }"
        >
          <input
            v-model="experienceBucket"
            type="radio"
            name="experience-bucket"
            class="seg-radio"
            :value="bucket.value"
          />
          {{ bucket.label }}
        </label>
      </div>
    </fieldset>

    <p v-if="loadError" class="form-error">Couldn't load options. Try reloading the page.</p>

    <div class="nav-row">
      <p v-if="saveError" class="form-error save-error">{{ saveError }}</p>
      <button
        type="button"
        class="btn primary"
        :class="{ disabled: !canContinue }"
        :disabled="!canContinue || saving"
        @click="onContinue"
      >
        {{ saving ? "Saving…" : "Continue" }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import ChipRow from "./ChipRow.vue";
import {
  listFields,
  listRoles,
  updateMyProfile,
  type FieldOption,
  type RoleOption,
} from "@/api/client";

const emit = defineEmits<{ continue: [] }>();

// Storage values must match services/profile.py:EXPERIENCE_BUCKETS exactly;
// display labels (en dash) are presentation-only and never sent to the API.
const EXPERIENCE_BUCKETS = [
  { value: "0-2", label: "0–2 yrs" },
  { value: "3-5", label: "3–5 yrs" },
  { value: "6-10", label: "6–10 yrs" },
  { value: "10+", label: "10+ yrs" },
];

const fields = ref<FieldOption[]>([]);
const roles = ref<RoleOption[]>([]);

const fieldName = ref<string | null>(null);
const fieldIsOther = ref(false);
const fieldOtherText = ref("");

const roleName = ref<string | null>(null);
const roleIsOther = ref(false);
const roleOtherText = ref("");

const experienceBucket = ref<string | null>(null);

const saving = ref(false);
const loadError = ref(false);
const saveError = ref("");

/** A row is satisfied by a curated pick, or by "Other" with non-blank text. */
function satisfied(selected: string | null, isOther: boolean, otherText: string): boolean {
  return isOther ? otherText.trim().length > 0 : selected !== null;
}

const fieldSatisfied = computed(() =>
  satisfied(fieldName.value, fieldIsOther.value, fieldOtherText.value),
);
const roleSatisfied = computed(() =>
  satisfied(roleName.value, roleIsOther.value, roleOtherText.value),
);
const canContinue = computed(
  () => fieldSatisfied.value && roleSatisfied.value && experienceBucket.value !== null,
);

/** The curated Field behind the current pick, or null when it's "Other" text. */
const selectedField = computed(() =>
  fieldIsOther.value ? null : (fields.value.find((f) => f.name === fieldName.value) ?? null),
);

const rolesLoading = ref(false);

const rolePlaceholder = computed(() => {
  if (!fieldSatisfied.value) return "Pick a field first";
  if (rolesLoading.value) return "Loading roles…";
  return null;
});

// Changing the Field invalidates the Role: its options are Field-scoped, so a
// role kept from the previous Field would no longer belong to anything.
// The token discards a slow in-flight fetch whose Field is no longer selected,
// which would otherwise repopulate the row with the previous Field's roles.
let rolesFetchToken = 0;

watch([fieldName, fieldIsOther], async () => {
  const token = ++rolesFetchToken;

  roleName.value = null;
  roleIsOther.value = false;
  roleOtherText.value = "";
  roles.value = [];

  const field = selectedField.value;
  if (!field) return; // an "Other" Field has no curated roles by definition

  // The Role fetch now merges in an LLM call (Role and Prompt Suggestions
  // story), so it can take noticeably longer than the old DB-only read —
  // without this, the row just looks empty/broken for that stretch.
  rolesLoading.value = true;
  try {
    const fetched = await listRoles(field.id);
    if (token === rolesFetchToken) roles.value = fetched;
  } catch {
    if (token === rolesFetchToken) loadError.value = true;
  } finally {
    if (token === rolesFetchToken) rolesLoading.value = false;
  }
});

async function onContinue() {
  if (!canContinue.value || saving.value) return;
  saving.value = true;
  saveError.value = "";
  try {
    await updateMyProfile({
      fieldName: fieldIsOther.value ? fieldOtherText.value.trim() : (fieldName.value as string),
      fieldIsOther: fieldIsOther.value,
      roleName: roleIsOther.value ? roleOtherText.value.trim() : (roleName.value as string),
      roleIsOther: roleIsOther.value,
      experienceBucket: experienceBucket.value,
    });
    emit("continue");
  } catch {
    saveError.value = "Couldn't save. Check your connection and try again.";
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
.row-gap {
  margin-top: 28px;
}

/* Mirrors ChipRow.vue's .block-head/.step-num/.step-label — scoped styles
   don't cross components, so this is intentionally duplicated rather than a
   ChipRow API change (Experience isn't a chip row, it doesn't belong there). */
.exp-fieldset {
  border: none;
  padding: 0;
  margin: 28px 0 0;
}
.block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 0 16px;
  padding: 0;
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

.seg-row {
  display: flex;
  gap: 2px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 3px;
}
.seg {
  position: relative;
  flex: 1;
  text-align: center;
  padding: 9px 0;
  border-radius: 8px;
  font-size: 13px;
  color: #8b93a7;
  cursor: pointer;
  transition: all 0.18s ease;
}
.seg.selected {
  background: rgba(109, 123, 255, 0.18);
  color: #fff;
}
.seg:focus-within {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  .seg {
    transition: none;
  }
}

/* Visually hidden but focusable — real radio semantics (arrow-key movement
   within the group, single tab stop) come from these inputs; display:none
   would drop them from the tab order entirely. */
.seg-radio {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.form-error {
  color: #8b93a7;
  font-size: 12px;
  margin: 12px 0 0;
}
.save-error {
  margin: 0;
}

.nav-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
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
.btn:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 2px;
}
.btn.primary {
  background: linear-gradient(180deg, #7b86ff, #5c68e8);
  color: #fff;
  box-shadow: 0 10px 24px -10px rgba(109, 123, 255, 0.6);
}
/* Native :disabled, so the gate also removes it from the tab order — the old
   pointer-events:none left keyboard users pressing Enter into silence. */
.btn.primary:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
}
</style>
