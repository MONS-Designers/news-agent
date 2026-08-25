<template>
  <div>
    <ChipRow
      step-num="1"
      label="תחום"
      :options="fields"
      other-placeholder="לדוגמה: ביולוגיה ימית"
      :placeholder-text="null"
      v-model:selected-name="fieldName"
      v-model:is-other="fieldIsOther"
      v-model:other-text="fieldOtherText"
    />

    <div class="mt-7">
      <ChipRow
        step-num="2"
        label="תפקיד"
        :options="roles"
        other-placeholder="לדוגמה: יחסי מפתחים"
        :placeholder-text="rolePlaceholder"
        v-model:selected-name="roleName"
        v-model:is-other="roleIsOther"
        v-model:other-text="roleOtherText"
      />
    </div>

    <fieldset class="mt-7 border-0 p-0">
      <legend class="mb-4 flex items-center gap-2.5 p-0">
        <span
          class="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-hd-accent-2/16 text-[11px] font-bold text-hd-accent"
          >3</span
        >
        <span class="text-[11px] font-bold uppercase tracking-[2px] text-hd-label">ניסיון</span>
      </legend>
      <div class="flex gap-0.5 rounded-[10px] border border-white/[0.08] bg-white/[0.03] p-[3px]">
        <label
          v-for="bucket in EXPERIENCE_BUCKETS"
          :key="bucket.value"
          :class="[
            'relative flex min-h-[44px] flex-1 cursor-pointer items-center justify-center rounded-lg py-[9px] text-center text-[13px] motion-reduce:transition-none [transition:all_0.18s_ease] focus-within:outline focus-within:outline-2 focus-within:outline-hd-accent-2 focus-within:outline-offset-2',
            experienceBucket === bucket.value ? 'bg-hd-accent-2/18 text-white' : 'text-hd-subtitle',
          ]"
        >
          <input
            v-model="experienceBucket"
            type="radio"
            name="experience-bucket"
            class="sr-only"
            :value="bucket.value"
          />
          {{ bucket.label }}
        </label>
      </div>
    </fieldset>

    <p v-if="loadError" class="mt-3 text-xs text-hd-subtitle">טעינת האפשרויות נכשלה. אפשר לרענן את הדף.</p>

    <div class="mt-7 flex items-center justify-end gap-3.5">
      <p v-if="saveError" class="text-xs text-hd-subtitle">{{ saveError }}</p>
      <button
        type="button"
        class="inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border-0 bg-gradient-to-b from-[#7b86ff] to-[#5c68e8] px-[22px] py-[11px] text-[13.5px] font-semibold text-white [font-family:inherit] [transition:transform_0.18s_ease] motion-reduce:transition-none shadow-[0_10px_24px_-10px_rgba(109,123,255,0.6)] active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-35 disabled:shadow-none disabled:active:scale-100"
        :class="{ disabled: !canContinue }"
        :disabled="!canContinue || saving"
        @click="onContinue"
      >
        {{ saving ? "שומר…" : "המשך" }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import ChipRow from "./ChipRow.vue";
import {
  getMyProfile,
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
  { value: "0-2", label: "0–2 שנים" },
  { value: "3-5", label: "3–5 שנים" },
  { value: "6-10", label: "6–10 שנים" },
  { value: "10+", label: "10+ שנים" },
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

const pendingRolePrefill = ref<string | null>(null);

const initialSnapshot = ref<{
  field: string | null;
  role: string | null;
  experienceBucket: string | null;
} | null>(null);

function effectiveField(): string | null {
  return fieldIsOther.value ? fieldOtherText.value.trim() : fieldName.value;
}
function effectiveRole(): string | null {
  return roleIsOther.value ? roleOtherText.value.trim() : roleName.value;
}
function captureSnapshot() {
  initialSnapshot.value = {
    field: effectiveField(),
    role: effectiveRole(),
    experienceBucket: experienceBucket.value,
  };
}

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
  if (!fieldSatisfied.value) return "בחר תחום קודם";
  if (rolesLoading.value) return "טוען תפקידים…";
  return null;
});

// Changing the Field invalidates the Role: its options are Field-scoped, so a
// role kept from the previous Field would no longer belong to anything.
// The token discards a slow in-flight fetch whose Field is no longer selected,
// which would otherwise repopulate the row with the previous Field's roles.
let rolesFetchToken = 0;

watch([fieldName, fieldIsOther], async () => {
  const token = ++rolesFetchToken;
  const rolePrefill = pendingRolePrefill.value;
  pendingRolePrefill.value = null;

  roleName.value = null;
  roleIsOther.value = false;
  roleOtherText.value = "";
  roles.value = [];

  const field = selectedField.value;
  if (!field) {
    // A stale in-flight fetch from a previously-selected curated Field would
    // otherwise never reach its own `finally` (its token no longer matches),
    // leaving the "טוען תפקידים…" placeholder stuck on forever.
    rolesLoading.value = false;
    if (rolePrefill !== null) captureSnapshot(); // "Other" Field pre-fill, no Role row to resolve
    return; // an "Other" Field has no curated roles by definition
  }

  // The Role fetch now merges in an LLM call (Role and Prompt Suggestions
  // story), so it can take noticeably longer than the old DB-only read -
  // without this, the row just looks empty/broken for that stretch.
  rolesLoading.value = true;
  try {
    const fetched = await listRoles(field.id);
    if (token === rolesFetchToken) {
      roles.value = fetched;
      if (rolePrefill !== null) {
        const match = fetched.find((r) => r.name === rolePrefill);
        if (match) {
          roleName.value = match.name;
          roleIsOther.value = false;
        } else {
          roleName.value = rolePrefill;
          roleIsOther.value = true;
          roleOtherText.value = rolePrefill;
        }
        captureSnapshot();
      }
    }
  } catch {
    if (token === rolesFetchToken) loadError.value = true;
  } finally {
    if (token === rolesFetchToken) rolesLoading.value = false;
  }
});

async function onContinue() {
  if (!canContinue.value || saving.value) return;

  if (
    initialSnapshot.value &&
    initialSnapshot.value.field === effectiveField() &&
    initialSnapshot.value.role === effectiveRole() &&
    initialSnapshot.value.experienceBucket === experienceBucket.value
  ) {
    emit("continue");
    return;
  }

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
    captureSnapshot();
    emit("continue");
  } catch {
    saveError.value = "השמירה נכשלה. ניתן לבדוק את החיבור ולנסות שוב.";
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    const [fetchedFields, profile] = await Promise.all([listFields(), getMyProfile()]);
    fields.value = fetchedFields;
    experienceBucket.value = profile.experience_bucket;

    if (profile.field_name === null) {
      captureSnapshot(); // brand-new user - nothing to pre-fill, snapshot is all-blank
      return;
    }

    pendingRolePrefill.value = profile.role_name;
    const curated = fetchedFields.some((f) => f.name === profile.field_name);
    if (curated) {
      fieldName.value = profile.field_name;
      fieldIsOther.value = false;
    } else {
      fieldName.value = profile.field_name;
      fieldIsOther.value = true;
      fieldOtherText.value = profile.field_name;
    }
  } catch {
    loadError.value = true;
  }
});
</script>
