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
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const orbA = ref<HTMLElement | null>(null);
const orbB = ref<HTMLElement | null>(null);
const orbC = ref<HTMLElement | null>(null);

// Mouse + scroll driven parallax. Both handlers recompute each orb's full
// transform from current state - never append to the existing transform
// string (that grows unbounded and freezes the tab under fast/repeated
// scroll events - learned the hard way in the UX prototype).
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
// (a tap has no "position to hover from") - only attach/detach it for
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
