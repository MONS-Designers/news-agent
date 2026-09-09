<template>
  <!--
    A floor under the surface so it stops resizing under the reader as they
    move between states - loading would otherwise collapse it to a single
    line, and the summary, each wizard step, and the error banner are all
    different heights. The floor is the screen below the app header, or
    56rem, whichever is larger: on a tall window the surface simply fills it,
    and on a short one 56rem still clears every state's natural height at
    desktop widths (measured: summary 855px, tallest wizard step 764px).
    A phone, or an unusually long interests paragraph, still scrolls past it.
  -->
  <HybridDepthBackground class="min-h-[max(calc(100vh-8rem),56rem)]">
    <div class="mb-7">
      <p class="mb-2.5 text-[11px] font-bold uppercase tracking-[3px] text-hd-kicker">העדפות</p>
      <h1 class="mb-2.5 text-[26px] font-[650] tracking-[-0.5px] text-hd-title sm:text-[30px]">
        {{ headingTitle }}
      </h1>
      <p class="max-w-[52ch] text-sm leading-[1.55] text-hd-subtitle">{{ headingSubtitle }}</p>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-sm text-hd-subtitle">
      <HybridSpinner size="standalone" /> טעינה…
    </div>

    <!-- Accent-tinted alert frame, not red/amber: DESIGN.md's anti-pattern
         table bans any second chromatic hue for warnings and errors inside
         Hybrid Depth. Same treatment as the topics-stale box below. -->
    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-hd-accent-2/40 bg-hd-accent-2/[0.14] px-5 py-[18px] text-[13.5px] leading-[1.55] text-hd-body"
    >
      {{ errorMessage }}
    </div>

    <div v-else-if="showSummary" class="flex flex-col gap-[18px]">
      <div
        v-if="topicsStale"
        class="rounded-xl border border-hd-accent-2/40 bg-hd-accent-2/[0.14] px-5 py-[18px]"
      >
        <p class="mb-1.5 text-[13.5px] font-semibold leading-[1.55] text-hd-title">
          שינית את הפרופיל, אבל הנושאים נשארו כפי שהיו.
        </p>
        <p class="text-[13.5px] leading-[1.55] text-hd-body">
          הנושאים שלמטה נבחרו לפי התשובות הקודמות שלך, ולכן {{ DIGEST_NOUN_WEEKLY }} עדיין נבנה
          סביבן. אפשר לרענן אותם בהתאם לפרופיל החדש.
        </p>
        <button type="button" :class="[BTN_PRIMARY, 'mt-3.5']" @click="editing = true">
          עדכון הנושאים שלי
        </button>
      </div>

      <div class="rounded-2xl border border-white/[0.09] bg-white/[0.035] p-4 backdrop-blur-[18px] sm:p-[30px]">
        <dl class="mb-6 grid grid-cols-1 gap-x-6 gap-y-3.5 sm:grid-cols-2">
          <div>
            <dt class="mb-1 text-[11px] tracking-[1px] text-hd-subtitle">תחום</dt>
            <dd class="text-sm font-semibold text-hd-fg">{{ profile?.field_name }}</dd>
          </div>
          <div>
            <dt class="mb-1 text-[11px] tracking-[1px] text-hd-subtitle">תפקיד</dt>
            <dd class="text-sm font-semibold text-hd-fg">{{ profile?.role_name }}</dd>
          </div>
          <div>
            <dt class="mb-1 text-[11px] tracking-[1px] text-hd-subtitle">ניסיון</dt>
            <dd class="text-sm font-semibold text-hd-fg">{{ experienceLabel }}</dd>
          </div>
          <div v-if="profile?.interest_free_text" class="sm:col-span-2">
            <dt class="mb-1 text-[11px] tracking-[1px] text-hd-subtitle">תחומי עניין</dt>
            <dd class="text-sm font-normal text-hd-body">{{ profile.interest_free_text }}</dd>
          </div>
        </dl>

        <div>
          <p class="mb-2.5 text-[13px] text-hd-subtitle">נושאים רשומים</p>
          <div class="mb-6 flex flex-wrap gap-2.5">
            <span
              v-for="topic in subscribedTopics"
              :key="topic.topic_id"
              :class="TOPIC_READONLY_PICKED"
            >
              {{ topic.name }}
            </span>
            <span v-if="subscribedTopics.length === 0" class="text-xs text-hd-muted">עדיין אין</span>
          </div>
        </div>

        <button type="button" :class="BTN_PRIMARY" @click="editing = true">עריכת פרופיל</button>
      </div>

      <div
        class="flex flex-col items-stretch gap-3.5 rounded-2xl border border-white/[0.09] bg-white/[0.035] px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-5"
      >
        <div>
          <p class="mb-1 text-sm font-semibold text-hd-fg">מיילים שבועיים</p>
          <p :class="['text-xs', subscription?.unsubscribed ? 'text-hd-accent' : 'text-hd-subtitle']">
            {{ subscription?.unsubscribed ? `מושהה - ${DIGEST_NOUN_WEEKLY} לא יישלח.` : "פעיל" }}
          </p>
        </div>
        <button
          type="button"
          :disabled="subscriptionSaving"
          :class="[BTN_SECONDARY, 'self-start sm:self-auto']"
          @click="toggleSubscription"
        >
          {{ subscription?.unsubscribed ? "המשך" : "השהיה" }}
        </button>
      </div>
    </div>

    <ProfilePickerShell
      v-else
      :can-exit="canExitWizard"
      @topics-saved="refreshPreferencesQuietly"
      @back="editing = false"
    />
  </HybridDepthBackground>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ApiError,
  getMyProfile,
  getMySubscription,
  listMyPreferences,
  updateMySubscription,
  type Subscription,
} from "@/api/client";
import HybridDepthBackground from "@/components/HybridDepthBackground.vue";
import HybridSpinner from "@/components/HybridSpinner.vue";
import ProfilePickerShell from "@/components/profile-picker/ProfilePickerShell.vue";
import { DIGEST_NOUN_WEEKLY } from "@/branding";
import { profileDraft as profile, preferencesDraft as preferences, initProfileDraft } from "@/profile-draft";

// Reused verbatim from TopicsStep.vue / AboutYouStep.vue (see those files) -
// the edit-profile button and the topics-stale alert's action button.
const BTN_BASE =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border-0 text-[13.5px] font-semibold [font-family:inherit] [transition:transform_0.18s_ease] motion-reduce:transition-none active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:active:scale-100";
const BTN_PRIMARY = `${BTN_BASE} px-[22px] py-[11px] [background-image:linear-gradient(to_bottom_in_oklch,_#434ed2,_#231666)] border-[1px] border-[#a9b1ff]/30 text-white shadow-[0_4px_12px_-6px_rgba(109,123,255,0.35)] disabled:opacity-35 disabled:shadow-none`;

// New combo (no existing button-secondary in the codebase yet) - bordered/
// unfilled, between BTN_GHOST (too weak) and BTN_PRIMARY (too heavy), for
// the subscription-toggle button. Same sizing/focus-visible/motion-reduce
// conventions as BTN_BASE, but with a visible border (BTN_BASE uses
// border-0, since primary/ghost don't want one).
const BTN_SECONDARY =
  "inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center justify-center rounded-[10px] border border-white/[0.09] px-[18px] py-[9px] text-[13.5px] font-semibold [font-family:inherit] text-hd-subtitle bg-white/[0.02] [transition:transform_0.18s_ease,background-color_0.18s_ease,border-color_0.18s_ease] motion-reduce:transition-none active:scale-[0.97] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:active:scale-100 disabled:opacity-35 [@media(hover:hover)]:hover:border-white/[0.22] [@media(hover:hover)]:hover:bg-white/[0.05]";

// TOPIC_BASE/TOPIC_PICKED reused verbatim from TopicsStep.vue, minus
// cursor-pointer/active:scale-[0.97] - these pills are read-only (no click
// handler, no "✕").
const TOPIC_BASE_READONLY =
  "inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border px-4 py-[9px] text-[13.5px] [font-family:inherit] motion-reduce:transition-none [transition:border-color_0.18s_ease,background_0.18s_ease,transform_0.18s_ease] focus-visible:outline focus-visible:outline-2 focus-visible:outline-hd-accent-2 focus-visible:outline-offset-2";
const TOPIC_PICKED =
  "border-hd-accent-2/50 bg-gradient-to-b from-hd-accent-2/32 to-hd-accent-2/14 text-white";
const TOPIC_READONLY_PICKED = `${TOPIC_BASE_READONLY} ${TOPIC_PICKED}`;

const subscription = ref<Subscription | null>(null);
const subscriptionSaving = ref(false);
// `loading` is component-local, so it would reset to true on every fresh
// mount (every SPA navigation back to this route) regardless of what
// profileDraft already knows - initialize it from the store's current state,
// not a hardcoded true, so a revisit with already-known data never flashes
// the spinner at all (see loadPreferences()'s matching `alreadyKnown` check).
const loading = ref(profile.value === null);
const errorMessage = ref("");

// A returning user with a completed profile sees a read-only summary first,
// not the wizard - editing (and the suggestion-recompute logic it can
// trigger) only happens when they explicitly choose to.
const editing = ref(false);

// Latched by the first load when it finds no saved profile, and never
// recomputed from one. Step 1 writes field_name the moment the user presses
// Continue, so deriving "should the wizard be showing" from the stored
// profile alone would swap the wizard out for the summary in the middle of
// onboarding - between Step 1 and Step 2.
const onboarding = ref(false);

const showSummary = computed(
  () => !editing.value && !onboarding.value && !!profile.value?.field_name,
);
const topicsStale = computed(() => !!profile.value?.topics_stale_at);

// The wizard is the chain's last branch. Naming it lets the heading and the
// cancel button read the same state the template's v-else does, without
// switching the title for the split second before the first fetch resolves.
const showWizard = computed(() => !loading.value && !errorMessage.value && !showSummary.value);

// Stepping back off the wizard's first step only has somewhere to land when
// the wizard was opened from the summary. A user still onboarding has no
// summary behind it - not even after Step 1 saves - so that step shows no
// Back for them.
const canExitWizard = computed(() => editing.value);

// One heading owns the screen, swapping text per state. ProfilePickerShell
// used to carry its own title, which stacked two headings on top of each
// other the moment the wizard opened.
const headingTitle = computed(() =>
  showWizard.value ? "הגדרת הפרופיל שלך" : "העדפות הנושאים שלי",
);
const headingSubtitle = computed(() =>
  showWizard.value
    ? "שלושה שלבים מהירים. אפשר לשנות כל דבר אחר כך - שום דבר לא ננעל."
    // Phrased to avoid a "ב" prefix on DIGEST_NOUN_WEEKLY - the constant
    // already carries its own definite "ה", and the old wording rendered as
    // "בהדייג'סט השבועי".
    : `${DIGEST_NOUN_WEEKLY} שלך נבנה מהנושאים שנבחרו כאן.`,
);

// Mirrors AboutYouStep.vue's EXPERIENCE_BUCKETS display labels.
const EXPERIENCE_LABELS: Record<string, string> = {
  "0-2": "0–2 שנים",
  "3-5": "3–5 שנים",
  "6-10": "6–10 שנים",
  "10+": "10+ שנים",
};
const experienceLabel = computed(() => {
  const bucket = profile.value?.experience_bucket;
  return bucket ? (EXPERIENCE_LABELS[bucket] ?? bucket) : "-";
});

const subscribedTopics = computed(() => preferences.value.filter((topic) => topic.subscribed));

async function loadPreferences() {
  // profileDraft survives SPA navigation (it's a module-level ref, not
  // component state) - so returning to /preferences after visiting another
  // route within the same tab already has valid data sitting in the store.
  // Only block on a real loading state for the first-ever fetch this tab has
  // done; a revisit re-validates quietly in the background instead of
  // flashing the loading spinner over data that's already on screen.
  const alreadyKnown = profile.value !== null;
  if (!alreadyKnown) loading.value = true;
  errorMessage.value = "";
  try {
    const [prefs, prof, sub] = await Promise.all([
      listMyPreferences(),
      getMyProfile(),
      getMySubscription(),
    ]);
    initProfileDraft(prof, prefs);
    subscription.value = sub;
    // Only the first load decides this - see `onboarding`'s declaration for
    // why it must not be recomputed once the wizard is running.
    if (!alreadyKnown) onboarding.value = !prof.field_name;
  } catch (error) {
    // A background revalidation failure is silent - what's already shown is
    // still the last known-good state. Only a first-ever load surfaces this.
    if (!alreadyKnown) {
      if (error instanceof ApiError && error.status === 401) {
        errorMessage.value = "יש להתחבר עם Google כדי לצפות בהעדפות שלך.";
      } else if (error instanceof ApiError && error.status === 403) {
        errorMessage.value = "לחשבון הזה אין פרופיל משתמש. ניתן לפנות למנהל המערכת.";
      } else {
        errorMessage.value = "טעינת ההעדפות נכשלה.";
      }
    }
  } finally {
    if (!alreadyKnown) loading.value = false;
  }
}

async function refreshPreferencesQuietly() {
  // Unlike loadPreferences, does not touch `loading` - that flag gates
  // ProfilePickerShell behind v-if, so toggling it here would destroy and
  // recreate the whole guided flow (resetting it to Step 1) right after the
  // user just finished it. This just re-syncs the preferences ref.
  try {
    preferences.value = await listMyPreferences();
  } catch {
    // Best-effort background refresh - the guided flow's own save already
    // succeeded and showed its own feedback; a failed refresh here shouldn't
    // interrupt anything.
  }
}

async function toggleSubscription() {
  if (!subscription.value) return;
  subscriptionSaving.value = true;
  try {
    subscription.value = await updateMySubscription(!subscription.value.unsubscribed);
  } catch {
    // Best-effort - leave the displayed state as-is on failure, no separate
    // error banner for a single toggle.
  } finally {
    subscriptionSaving.value = false;
  }
}

onMounted(loadPreferences);
</script>
