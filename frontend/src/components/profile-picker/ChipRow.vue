<template>
  <div>
    <div class="mb-4 flex items-center gap-2.5">
      <span
        class="flex h-[22px] w-[22px] items-center justify-center rounded-md bg-hd-accent-2/16 text-[11px] font-bold text-hd-accent"
        >{{ stepNum }}</span
      >
      <span class="text-[11px] font-bold uppercase tracking-[2px] text-hd-label">{{ label }}</span>
    </div>

    <p v-if="placeholderText" class="text-[13.5px] text-hd-muted">{{ placeholderText }}</p>

    <div v-else class="flex flex-wrap gap-2.5" role="group" :aria-label="label">
      <button
        v-for="option in options"
        :key="option.id ?? option.name"
        type="button"
        :class="chipClasses(isChipSelected(option))"
        :aria-pressed="isChipSelected(option)"
        @click="selectChip(option)"
      >
        {{ option.name }}
      </button>
      <button
        type="button"
        :class="chipClasses(otherButtonActive, { dashed: !otherButtonActive })"
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
      class="mt-3 w-full rounded-[10px] border border-hd-accent-2/40 bg-hd-accent-2/[0.06] px-3.5 py-[11px] text-[13.5px] text-hd-fg [font-family:inherit] placeholder:text-hd-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2"
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

const CHIP_BASE =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border px-4 py-[11px] text-[13.5px] [font-family:inherit] motion-reduce:transition-none [transition:border-color_0.18s_ease,background_0.18s_ease,transform_0.18s_ease] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 active:scale-[0.97]";
// Hover styles are gated behind `hover:hover` so tapping on a touchscreen never
// leaves a chip stuck in its hover-lit state (the classic mobile Safari/Chrome
// sticky-:hover bug) — only pointers that can sustain hover (a mouse) get it.
const CHIP_UNSELECTED =
  "border-white/[0.09] bg-white/[0.02] [@media(hover:hover)]:hover:border-white/[0.22] [@media(hover:hover)]:hover:bg-white/[0.05] motion-safe:[@media(hover:hover)]:hover:-translate-y-px";
const CHIP_SELECTED =
  "border-hd-accent-2/55 bg-gradient-to-b from-hd-accent-2/22 to-hd-accent-2/10 text-white shadow-[0_0_0_1px_rgba(109,123,255,0.25),0_8px_24px_-8px_rgba(109,123,255,0.45)]";

/** Shared chip styling; `dashed` marks the "Other" button's idle (not-yet-active) state. */
function chipClasses(selected: boolean, opts: { dashed?: boolean } = {}): string {
  const isDashed = !!opts.dashed && !selected;
  const textColor = selected ? "" : isDashed ? "text-hd-subtitle" : "text-hd-chip";
  const borderStyle = isDashed ? "border-dashed" : "";
  return [CHIP_BASE, selected ? CHIP_SELECTED : CHIP_UNSELECTED, textColor, borderStyle]
    .filter(Boolean)
    .join(" ");
}
</script>
