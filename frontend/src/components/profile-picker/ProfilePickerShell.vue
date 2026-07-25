<template>
  <div class="picker-shell">
    <div class="depth-field" aria-hidden="true">
      <div ref="orbA" class="orb orb-a"></div>
      <div ref="orbB" class="orb orb-b"></div>
      <div ref="orbC" class="orb orb-c"></div>
    </div>
    <div class="grain" aria-hidden="true"></div>

    <div class="content">
      <p class="kicker">Preferences</p>
      <h2 class="title">Set up your profile</h2>
      <p class="subtitle">Three quick steps. Change any of it later — this never locks in.</p>

      <ol class="stepper" aria-label="Setup progress">
        <li
          v-for="step in steps"
          :key="step.n"
          class="step"
          :class="{ active: step.n === currentStep, done: step.n < currentStep }"
        >
          <span class="step-dot">{{ step.n }}</span>
          <span class="step-label">{{ step.label }}</span>
        </li>
      </ol>

      <div class="panel" :key="currentStep">
        <div v-if="currentStep === 1" class="stagger">
          <FieldStep @continue="currentStep = 2" />
        </div>
        <div v-else-if="currentStep === 2" class="stagger">
          <p class="placeholder">Interests step — coming in a later story.</p>
        </div>
        <div v-else class="stagger">
          <p class="placeholder">Topics step — coming in a later story.</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import FieldStep from "./FieldStep.vue";

const steps = [
  { n: 1, label: "About you" },
  { n: 2, label: "Interests" },
  { n: 3, label: "Topics" },
];

const currentStep = ref(1);

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

function onScroll() {
  scrollY = window.scrollY;
  applyOrbTransforms();
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

onMounted(() => {
  motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  handleMotionChange(motionQuery);
  motionQuery.addEventListener("change", handleMotionChange);

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("scroll", onScroll, { passive: true });
});

onBeforeUnmount(() => {
  window.removeEventListener("mousemove", onMouseMove);
  window.removeEventListener("scroll", onScroll);
  motionQuery?.removeEventListener("change", handleMotionChange);
});
</script>

<style scoped>
/*
  Hybrid Depth tokens, per DESIGN.md. This section is the first custom visual
  identity in the live app — deliberately scoped to this component only, not
  a global restyle (the rest of PreferencesView keeps its plain Tailwind look).
*/
.picker-shell {
  position: relative;
  background: #0a0d16;
  color: #eef1f8;
  border-radius: 16px;
  padding: 30px;
  overflow: hidden;
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Inter,
    Arial,
    sans-serif;
}

.depth-field {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.35;
  will-change: transform;
}
.orb-a {
  width: 460px;
  height: 460px;
  top: -120px;
  left: -80px;
  background: radial-gradient(circle, #4b3fae, transparent 70%);
}
.orb-b {
  width: 380px;
  height: 380px;
  top: 40%;
  right: -100px;
  background: radial-gradient(circle, #1f6f78, transparent 70%);
}
.orb-c {
  width: 340px;
  height: 340px;
  bottom: -140px;
  left: 30%;
  background: radial-gradient(circle, #7a3b6e, transparent 70%);
}

.grain {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.35;
  background-image: radial-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 26px 26px;
}

.content {
  position: relative;
  z-index: 2;
}

.kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #6d7bff;
  margin: 0 0 10px;
}
.title {
  font-size: 30px;
  font-weight: 650;
  letter-spacing: -0.5px;
  margin: 0 0 10px;
  color: #f4f6fb;
}
.subtitle {
  font-size: 14px;
  color: #8b93a7;
  line-height: 1.55;
  margin: 0 0 28px;
  max-width: 52ch;
}

.stepper {
  display: flex;
  align-items: center;
  gap: 8px;
  list-style: none;
  margin: 0 0 28px;
  padding: 0;
}
.step {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}
.step-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: #565f74;
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.35s ease;
}
.step-label {
  font-size: 11px;
  color: #565f74;
  white-space: nowrap;
  transition: color 0.35s ease;
}
.step.active .step-dot {
  border-color: #6d7bff;
  color: #fff;
  background: rgba(109, 123, 255, 0.25);
  box-shadow: 0 0 0 4px rgba(109, 123, 255, 0.12);
}
.step.active .step-label {
  color: #c4cadb;
}
.step.done .step-dot {
  border-color: #6d7bff;
  background: #6d7bff;
  color: #fff;
}
.step.done .step-label {
  color: #8b93a7;
}

.panel {
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  padding: 30px;
  backdrop-filter: blur(18px);
}

.placeholder {
  color: #565f74;
  font-size: 13px;
  margin: 0;
}

.stagger {
  opacity: 0;
  transform: translateY(14px);
  animation: fadeUp 0.5s ease forwards;
}
@keyframes fadeUp {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .stagger {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
