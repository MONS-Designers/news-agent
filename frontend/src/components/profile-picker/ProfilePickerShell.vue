<template>
  <div class="relative overflow-hidden rounded-2xl bg-hd-bg p-4 font-hd text-hd-fg sm:p-[30px]">
    <div class="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
      <div
        ref="orbA"
        class="absolute h-[460px] w-[460px] top-[-120px] left-[-80px] rounded-full bg-[radial-gradient(circle,#4b3fae,transparent_70%)] opacity-35 blur-[70px] will-change-transform"
      ></div>
      <div
        ref="orbB"
        class="absolute h-[380px] w-[380px] top-[40%] right-[-100px] rounded-full bg-[radial-gradient(circle,#1f6f78,transparent_70%)] opacity-35 blur-[70px] will-change-transform"
      ></div>
      <div
        ref="orbC"
        class="absolute h-[340px] w-[340px] bottom-[-140px] left-[30%] rounded-full bg-[radial-gradient(circle,#7a3b6e,transparent_70%)] opacity-35 blur-[70px] will-change-transform"
      ></div>
    </div>
    <div
      class="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[length:26px_26px] opacity-35"
      aria-hidden="true"
    ></div>

    <div class="relative z-[2]">
      <p class="mb-2.5 text-[11px] font-bold uppercase tracking-[3px] text-hd-kicker">Preferences</p>
      <h2 class="mb-2.5 text-[30px] font-[650] tracking-[-0.5px] text-hd-title">Set up your profile</h2>
      <p class="mb-7 max-w-[52ch] text-sm leading-[1.55] text-hd-subtitle">
        Three quick steps. Change any of it later — this never locks in.
      </p>

      <ol class="mb-7 flex list-none items-center gap-2 p-0" aria-label="Setup progress">
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
          old "state dies on unmount" gap — an accidental side effect of
          destroy/recreate, not an intentional design). Entrance-animation
          replay is handled separately, below, so it no longer depends on
          destroying the DOM to work.
        -->
        <div ref="step1El" v-show="currentStep === 1" :class="STAGGER">
          <AboutYouStep @continue="currentStep = 2" />
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
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import AboutYouStep from "./AboutYouStep.vue";
import InterestsStep from "./InterestsStep.vue";
import TopicsStep from "./TopicsStep.vue";

const emit = defineEmits<{ "topics-saved": [] }>();

const steps = [
  { n: 1, label: "About you" },
  { n: 2, label: "Interests" },
  { n: 3, label: "Topics" },
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

const orbA = ref<HTMLElement | null>(null);
const orbB = ref<HTMLElement | null>(null);
const orbC = ref<HTMLElement | null>(null);

// Mouse + scroll driven parallax. Both handlers recompute each orb's full
// transform from current state — never append to the existing transform
// string (that grows unbounded and freezes the tab under fast/repeated
// scroll events — learned the hard way in the UX prototype).
const orbConfigs = [
  { depthX: 26, scrollFactor: 0.04 },
  { depthX: 40, scrollFactor: -0.06 },
  { depthX: 18, scrollFactor: 0.03 },
];
let mouseX = 0;
let mouseY = 0;
let scrollY = 0;
let reducedMotion = false;

function applyOrbTransforms() {
  if (reducedMotion) return;
  const orbs = [orbA.value, orbB.value, orbC.value];
  orbs.forEach((orb, i) => {
    if (!orb) return;
    const config = orbConfigs[i];
    const x = mouseX * config.depthX;
    const y = mouseY * config.depthX + scrollY * config.scrollFactor;
    orb.style.transform = `translate(${x}px, ${y}px)`;
  });
}

function onMouseMove(event: MouseEvent) {
  mouseX = event.clientX / window.innerWidth - 0.5;
  mouseY = event.clientY / window.innerHeight - 0.5;
  applyOrbTransforms();
}

// requestAnimationFrame-throttled: raw scroll events can fire far more often
// than once per frame (especially with momentum scrolling on mobile), and
// recomputing 3 transforms per event is wasted work the browser never gets
// to paint anyway.
let scrollRafId: number | null = null;
function onScroll() {
  if (scrollRafId !== null) return;
  scrollRafId = requestAnimationFrame(() => {
    scrollY = window.scrollY;
    applyOrbTransforms();
    scrollRafId = null;
  });
}

let motionQuery: MediaQueryList | null = null;
function handleMotionChange(event: MediaQueryListEvent | MediaQueryList) {
  reducedMotion = event.matches;
  if (reducedMotion) {
    [orbA.value, orbB.value, orbC.value].forEach((orb) => {
      if (orb) orb.style.transform = "translate(0, 0)";
    });
  }
}

// The mouse half of the parallax is meaningless without a persistent pointer
// (a tap has no "position to hover from") — only attach/detach it for
// devices that actually have one, reactively, so a 2-in-1 switching between
// touch and a plugged-in mouse still gets the right behavior. Scroll-position
// parallax is unaffected and keeps working on touch devices.
let hoverQuery: MediaQueryList | null = null;
let mouseListenerAttached = false;
function handleHoverChange(event: MediaQueryListEvent | MediaQueryList) {
  const canHover = event.matches;
  if (canHover && !mouseListenerAttached) {
    window.addEventListener("mousemove", onMouseMove);
    mouseListenerAttached = true;
  } else if (!canHover && mouseListenerAttached) {
    window.removeEventListener("mousemove", onMouseMove);
    mouseListenerAttached = false;
    mouseX = 0;
    mouseY = 0;
    applyOrbTransforms();
  }
}

// Panels are kept mounted via v-show (never destroyed — see the template
// comment), so the entrance animation no longer replays "for free" as a side
// effect of recreation. Restart it explicitly, the same way the approved
// mockup's own goStep() does: force a reflow between clearing and restoring
// the animation property.
function replayEntrance(el: HTMLElement | null) {
  if (!el || reducedMotion) return;
  el.style.animation = "none";
  void el.offsetWidth; // reflow — must be read, not optimized away
  el.style.animation = "";
}

watch(currentStep, async (step) => {
  await nextTick();
  replayEntrance(stepElements[step - 1]?.value ?? null);
});

onMounted(() => {
  motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  handleMotionChange(motionQuery);
  motionQuery.addEventListener("change", handleMotionChange);

  hoverQuery = window.matchMedia("(hover: hover) and (pointer: fine)");
  handleHoverChange(hoverQuery);
  hoverQuery.addEventListener("change", handleHoverChange);

  window.addEventListener("scroll", onScroll, { passive: true });
});

onBeforeUnmount(() => {
  if (mouseListenerAttached) window.removeEventListener("mousemove", onMouseMove);
  window.removeEventListener("scroll", onScroll);
  if (scrollRafId !== null) cancelAnimationFrame(scrollRafId);
  motionQuery?.removeEventListener("change", handleMotionChange);
  hoverQuery?.removeEventListener("change", handleHoverChange);
});
</script>
