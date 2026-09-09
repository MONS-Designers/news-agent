<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold tracking-tight">העדפות הנושאים שלי</h1>
      <p class="mt-1 text-sm text-neutral-500">
        בחירת הנושאים שיופיעו ב{{ DIGEST_NOUN_WEEKLY }} שלך.
      </p>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-sm text-neutral-500">
      <HybridSpinner size="standalone" /> טעינה…
    </div>

    <div
      v-else-if="errorMessage"
      class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
    >
      {{ errorMessage }}
    </div>

    <HybridDepthBackground v-else-if="showSummary">
      <div class="flex flex-col gap-[18px]">
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
    </HybridDepthBackground>

    <ProfilePickerShell v-else @topics-saved="refreshPreferencesQuietly" />
  </div>
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
const loading = ref(true);
const errorMessage = ref("");

// A returning user with a completed profile sees a read-only summary first,
// not the wizard - editing (and the suggestion-recompute logic it can
// trigger) only happens when they explicitly choose to.
const editing = ref(false);
const showSummary = computed(() => !editing.value && !!profile.value?.field_name);
const topicsStale = computed(() => !!profile.value?.topics_stale_at);

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
  loading.value = true;
  errorMessage.value = "";
  try {
    const [prefs, prof, sub] = await Promise.all([
      listMyPreferences(),
      getMyProfile(),
      getMySubscription(),
    ]);
    initProfileDraft(prof, prefs);
    subscription.value = sub;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      errorMessage.value = "יש להתחבר עם Google כדי לצפות בהעדפות שלך.";
    } else if (error instanceof ApiError && error.status === 403) {
      errorMessage.value = "לחשבון הזה אין פרופיל משתמש. ניתן לפנות למנהל המערכת.";
    } else {
      errorMessage.value = "טעינת ההעדפות נכשלה.";
    }
  } finally {
    loading.value = false;
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
