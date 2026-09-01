<template>
  <div class="home">
    <div class="depth-field" aria-hidden="true">
      <div ref="orbA" class="orb orb-a"></div>
      <div ref="orbB" class="orb orb-b"></div>
      <div ref="orbC" class="orb orb-c"></div>
    </div>
    <div class="grain" aria-hidden="true"></div>

    <section v-if="capacityFull" class="hero">
      <p class="kicker">NewsAgent · גרסת בטא</p>
      <h1 class="title">אנחנו במלוא התפוסה כרגע.</h1>
      <p class="subtitle">
        NewsAgent פתוח כרגע לקבוצה קטנה של משתמשים מוקדמים בזמן שאנחנו מכווננים את המערכת. שמרנו
        את כתובת המייל שלך - ההזמנה תישלח ברגע שיתפנה מקום.
      </p>
    </section>

    <template v-else>
      <section class="hero">
        <p class="kicker">NewsAgent · גרסת בטא</p>
        <template v-if="firstRun">
          <h1 class="title">נכנסת.<br />נשאר רק להגדיר את הפרופיל.</h1>
          <p class="subtitle">
            שתי דקות, פעם אחת - התחום שלך, התפקיד שלך, מה מעניין אותך. משם אנחנו בונים את
            {{ DIGEST_NOUN_WEEKLY }} הראשון שלך סביב מה שבאמת חשוב לך.
          </p>
        </template>
        <template v-else>
          <h1 class="title">דייג'סט אחד.<br />כל מה שחשוב לך.</h1>
          <p class="subtitle">
            בינה מלאכותית שקוראת את החדשות בשבילך - מזוקקת לדייג'סט אחד וממוקד בעברית, שמגיע כל
            שבוע, בנוי סביב מה שבאמת מעניין אותך.
          </p>
        </template>
        <button type="button" class="cta" @click="goToPreferences">
          {{ firstRun ? "נכיר, זה לוקח 2 דקות" : "אני רוצה להגדיר את הדייג'סט שלי" }}
          <span class="cta-arrow" aria-hidden="true">←</span>
        </button>
      </section>

      <section class="steps" ref="stepsSection">
        <article
          v-for="(step, index) in steps"
          :key="step.title"
          class="step-card"
          :class="{ revealed: revealed }"
          :style="{ transitionDelay: `${index * 90}ms` }"
          @mousemove="onCardTilt($event, index)"
          @mouseleave="onCardLeave(index)"
          :ref="(el) => setCardRef(el as HTMLElement | null, index)"
        >
          <span class="step-num">{{ index + 1 }}</span>
          <h2 class="step-title">{{ step.title }}</h2>
          <p class="step-body">{{ step.body }}</p>
        </article>
      </section>
    </template>

    <footer class="foot">
      <p class="foot-text">מגיע במייל. אין שום דבר אחר לבדוק.</p>
      <p class="foot-text"><a class="foot-link" href="/privacy.html">מדיניות פרטיות</a></p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getMyProfile } from "@/api/client";
import { ensureMe } from "@/auth";
import { DIGEST_NOUN_WEEKLY } from "@/branding";

const router = useRouter();
const route = useRoute();

const capacityFull = computed(() => route.query.error === "capacity_full");

// A freshly self-registered user (no profile yet, no digest history) sees a
// welcome/first-run beat here instead of the generic anonymous pitch
// (UX-DR6) - distinct from PreferencesView.vue's returning-user summary,
// which is a different screen entirely.
const firstRun = ref(false);

async function checkFirstRun() {
  const identity = await ensureMe();
  if (!identity || identity.user_id === null) return; // anonymous or admin-only
  try {
    const profile = await getMyProfile();
    firstRun.value = profile.field_name === null;
  } catch {
    // Best-effort - on failure, just show the default (non-first-run) content.
  }
}

function goToPreferences() {
  router.push("/preferences");
}

const steps = [
  {
    title: "הסיפור שלך",
    body: "התחום שלך, התפקיד שלך, מה שבאמת מעניין אותך - כמה דקות, פעם אחת.",
  },
  {
    title: "הוא קורא הכל",
    body: "מקורות מכל הרשת, מסוננים ומסוכמים לכדי מה שבאמת רלוונטי.",
  },
  {
    title: "דייג'סט מסודר נוחת אצלך במייל",
    body: "מייל אחד וממוקד כל שבוע. בלי פיד לגלול, בלי אפליקציה לפתוח.",
  },
];

// -- Depth: orb parallax (mirrors ProfilePickerShell.vue's Hybrid Depth
// technique) - recomputed from current state each event, never appended. --
const orbA = ref<HTMLElement | null>(null);
const orbB = ref<HTMLElement | null>(null);
const orbC = ref<HTMLElement | null>(null);
const orbConfigs = [
  { depthX: 30, scrollFactor: 0.05 },
  { depthX: 46, scrollFactor: -0.07 },
  { depthX: 20, scrollFactor: 0.035 },
];
let mouseX = 0;
let mouseY = 0;
let scrollY = 0;
let reducedMotion = false;

function applyOrbTransforms() {
  if (reducedMotion) return;
  [orbA.value, orbB.value, orbC.value].forEach((orb, i) => {
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

// -- Scroll reveal for the "how it works" cards --
const stepsSection = ref<HTMLElement | null>(null);
const revealed = ref(false);
let revealObserver: IntersectionObserver | null = null;

// -- Light 3D tilt: a restrained perspective tilt following the cursor
// within each card, released back to flat on mouse-leave. Small max angle
// deliberately - the brand brief calls for "serious and mysterious," not a
// showy tilt-card gimmick. --
const cardEls: (HTMLElement | null)[] = [];
function setCardRef(el: HTMLElement | null, index: number) {
  cardEls[index] = el;
}
const MAX_TILT_DEG = 6;

function onCardTilt(event: MouseEvent, index: number) {
  if (reducedMotion) return;
  const el = cardEls[index];
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const px = (event.clientX - rect.left) / rect.width - 0.5;
  const py = (event.clientY - rect.top) / rect.height - 0.5;
  el.style.transform = `perspective(700px) rotateX(${(-py * MAX_TILT_DEG).toFixed(2)}deg) rotateY(${(px * MAX_TILT_DEG).toFixed(2)}deg) translateY(-2px)`;
}

function onCardLeave(index: number) {
  const el = cardEls[index];
  if (!el) return;
  el.style.transform = "";
}

onMounted(() => {
  void checkFirstRun();

  motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  handleMotionChange(motionQuery);
  motionQuery.addEventListener("change", handleMotionChange);

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("scroll", onScroll, { passive: true });

  if (reducedMotion) {
    revealed.value = true;
  } else if (stepsSection.value) {
    revealObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          revealed.value = true;
          revealObserver?.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    revealObserver.observe(stepsSection.value);
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("mousemove", onMouseMove);
  window.removeEventListener("scroll", onScroll);
  motionQuery?.removeEventListener("change", handleMotionChange);
  revealObserver?.disconnect();
});
</script>

<style scoped>
/* Hybrid Depth identity (_bmad-output/planning-artifacts/ux-designs/ux-news-agent-2026-07-21/DESIGN.md),
   extended here from the profile-picker panel to a full landing page. */
.home {
  position: relative;
  min-height: 100vh;
  background: #0a0d16;
  color: #eef1f8;
  overflow-x: hidden;
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Inter,
    Arial,
    sans-serif;
}

.depth-field {
  position: fixed;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
  will-change: transform;
}
.orb-a {
  width: 560px;
  height: 560px;
  top: -160px;
  left: -120px;
  background: radial-gradient(circle, #4b3fae, transparent 70%);
}
.orb-b {
  width: 480px;
  height: 480px;
  top: 30%;
  right: -140px;
  background: radial-gradient(circle, #1f6f78, transparent 70%);
}
.orb-c {
  width: 420px;
  height: 420px;
  bottom: -180px;
  left: 25%;
  background: radial-gradient(circle, #7a3b6e, transparent 70%);
}

.grain {
  position: fixed;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  opacity: 0.35;
  background-image: radial-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-size: 26px 26px;
}

.hero {
  position: relative;
  z-index: 2;
  max-width: 720px;
  margin: 0 auto;
  padding: 15vh 24px 12vh;
  text-align: center;
}
.kicker {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: #6d7bff;
  margin: 0 0 18px;
}
.title {
  font-size: 44px;
  line-height: 1.12;
  font-weight: 650;
  letter-spacing: -0.5px;
  margin: 0 0 20px;
  color: #f4f6fb;
}
.subtitle {
  font-size: 16px;
  color: #8b93a7;
  line-height: 1.6;
  max-width: 46ch;
  margin: 0 auto 36px;
}

.cta {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 15px 30px;
  border-radius: 10px;
  border: none;
  font-size: 14.5px;
  font-weight: 600;
  font-family: inherit;
  color: #ffffff;
  background: linear-gradient(180deg, #7b86ff, #5c68e8);
  box-shadow: 0 14px 34px -12px rgba(109, 123, 255, 0.65);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 40px -12px rgba(109, 123, 255, 0.8);
}
.cta:focus-visible {
  outline: 2px solid #6d7bff;
  outline-offset: 3px;
}
.cta-arrow {
  transition: transform 0.2s ease;
}
.cta:hover .cta-arrow {
  transform: translateX(-3px);
}

.steps {
  position: relative;
  z-index: 2;
  max-width: 980px;
  margin: 0 auto;
  padding: 0 24px 16vh;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 22px;
}

.step-card {
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  padding: 28px 24px;
  backdrop-filter: blur(18px);
  opacity: 0;
  transform: translateY(24px);
  transition:
    opacity 0.6s ease,
    transform 0.6s ease,
    border-color 0.2s ease;
  will-change: transform;
}
.step-card.revealed {
  opacity: 1;
  transform: translateY(0);
}
.step-card:hover {
  border-color: rgba(255, 255, 255, 0.22);
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: rgba(109, 123, 255, 0.16);
  color: #a9b1ff;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 16px;
}
.step-title {
  font-size: 16px;
  font-weight: 650;
  color: #f4f6fb;
  margin: 0 0 8px;
}
.step-body {
  font-size: 13.5px;
  line-height: 1.55;
  color: #8b93a7;
  margin: 0;
}

.foot {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 0 24px 10vh;
}
.foot-text {
  font-size: 12px;
  color: #565f74;
  margin: 0;
}
.foot-text + .foot-text {
  margin-top: 8px;
}
.foot-link {
  color: #8b93a7;
}
.foot-link:hover {
  color: #a9b1ff;
}

@media (max-width: 760px) {
  .title {
    font-size: 32px;
  }
  .steps {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cta,
  .cta-arrow,
  .step-card {
    transition: none;
  }
  .step-card {
    opacity: 1;
    transform: none;
  }
}
</style>
