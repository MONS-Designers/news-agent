<template>
  <!--
    Kicker, heading and the Hybrid Depth background all belong to
    PreferencesView now - it owns the whole screen's chrome so the page has
    exactly one heading and one background, whichever state it's in. This
    component is the stepper and the step panel, nothing else.
  -->
  <div>
    <ol class="mb-7 flex list-none items-center gap-2 p-0" aria-label="התקדמות ההגדרה">
      <li v-for="step in steps" :key="step.n" class="flex min-w-0 flex-1 items-center gap-2">
        <span :class="stepDotClasses(step.n)">{{ step.n }}</span>
        <span :class="stepLabelClasses(step.n)">{{ step.label }}</span>
      </li>
    </ol>

    <div class="rounded-2xl border border-white/[0.09] bg-white/[0.035] p-4 backdrop-blur-[18px] sm:p-[30px]">
      <!--
        v-show, not v-if/v-else: these panels must never be unmounted, or
        AboutYouStep's Field/Role/Experience selections would be destroyed
        the moment the user leaves Step 1 (this was the actual cause of the
        old "state dies on unmount" gap - an accidental side effect of
        destroy/recreate, not an intentional design). Entrance-animation
        replay is handled separately, below, so it no longer depends on
        destroying the DOM to work.
      -->
      <div ref="step1El" v-show="currentStep === 1" :class="STAGGER">
        <AboutYouStep :show-back="canExit" @continue="currentStep = 2" @back="emit('back')" />
      </div>
      <div ref="step2El" v-show="currentStep === 2" :class="STAGGER">
        <InterestsStep :active="currentStep === 2" @continue="currentStep = 3" @back="currentStep = 1" />
      </div>
      <div ref="step3El" v-show="currentStep === 3" :class="STAGGER">
        <TopicsStep
          :active="currentStep === 3"
          @back="currentStep = 2"
          @saved="emit('topics-saved')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import AboutYouStep from "./AboutYouStep.vue";
import InterestsStep from "./InterestsStep.vue";
import TopicsStep from "./TopicsStep.vue";

// `canExit` says whether Back on Step 1 has anywhere to go - the shell owns
// navigation between steps, but stepping back off the first one leaves the
// wizard entirely, which only whoever opened it can decide and perform.
defineProps<{ canExit?: boolean }>();
const emit = defineEmits<{ "topics-saved": []; back: [] }>();

const steps = [
  { n: 1, label: "עליך" },
  { n: 2, label: "תחומי עניין" },
  { n: 3, label: "נושאים" },
];

const currentStep = ref(1);

const STAGGER =
  "translate-y-3.5 opacity-0 animate-fade-up motion-reduce:translate-y-0 motion-reduce:animate-none motion-reduce:opacity-100";

const STEP_DOT_BASE =
  "flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border text-[11px] font-bold [transition:all_0.35s_ease] motion-reduce:transition-none";
const STEP_LABEL_BASE = "text-[11px] [transition:color_0.35s_ease] motion-reduce:transition-none sm:whitespace-nowrap";

function stepDotClasses(n: number): string {
  if (n === currentStep.value) {
    return `${STEP_DOT_BASE} border-hd-accent-2 bg-hd-accent-2/25 text-white shadow-[0_0_0_4px_rgba(109,123,255,0.12)]`;
  }
  if (n < currentStep.value) {
    return `${STEP_DOT_BASE} border-hd-accent-2 bg-hd-accent-2 text-white`;
  }
  return `${STEP_DOT_BASE} border-white/[0.15] bg-white/[0.02] text-hd-muted`;
}

function stepLabelClasses(n: number): string {
  if (n === currentStep.value) return `${STEP_LABEL_BASE} text-hd-chip`;
  if (n < currentStep.value) return `${STEP_LABEL_BASE} text-hd-subtitle`;
  return `${STEP_LABEL_BASE} text-hd-muted`;
}

const step1El = ref<HTMLElement | null>(null);
const step2El = ref<HTMLElement | null>(null);
const step3El = ref<HTMLElement | null>(null);
const stepElements = [step1El, step2El, step3El];

// Panels are kept mounted via v-show (never destroyed - see the template
// comment), so the entrance animation no longer replays "for free" as a side
// effect of recreation. Restart it explicitly, the same way the approved
// mockup's own goStep() does: force a reflow between clearing and restoring
// the animation property. Reads prefers-reduced-motion directly (rather than
// sharing HybridDepthBackground's internal reducedMotion state) since the
// orb-parallax logic that owned that state now lives entirely inside that
// component - motion-reduce:animate-none on STAGGER already suppresses the
// animation via CSS regardless, this check just avoids the pointless reflow.
function replayEntrance(el: HTMLElement | null) {
  if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  el.style.animation = "none";
  void el.offsetWidth; // reflow - must be read, not optimized away
  el.style.animation = "";
}

watch(currentStep, async (step) => {
  await nextTick();
  replayEntrance(stepElements[step - 1]?.value ?? null);
});
</script>
