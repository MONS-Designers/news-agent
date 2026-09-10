<template>
  <div class="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
    <header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-4xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:gap-x-8 sm:px-6">
        <router-link
          to="/"
          dir="ltr"
          class="-mx-2 -my-1 flex items-center gap-2 rounded-lg px-2 py-1 text-lg font-semibold tracking-tight transition-all duration-300 ease-out hover:shadow-[0_6px_20px_-4px_rgba(240,180,41,0.5)]"
        >
          <img :src="logoMark" alt="" class="h-7 w-7 rounded-lg" />
          <span>News<span class="text-amber-500">Agent</span></span>
        </router-link>
        <nav
          class="flex gap-1"
          :class="{
            'order-last w-full overflow-x-auto sm:order-none sm:w-auto sm:overflow-visible':
              me?.is_admin,
          }"
        >
          <router-link
            v-if="me?.is_admin"
            to="/admin"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            exact-active-class="bg-neutral-100 text-neutral-900"
          >
            ניהול
          </router-link>
          <router-link
            v-if="me?.is_admin"
            to="/admin/taxonomy"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            טקסונומיה
          </router-link>
          <router-link
            v-if="me?.is_admin"
            to="/admin/engagement"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            מעורבות
          </router-link>
          <router-link
            v-if="me"
            to="/preferences"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            העדפות
          </router-link>
        </nav>
        <div class="ms-auto flex items-center gap-3">
          <template v-if="me">
            <span class="hidden text-sm text-neutral-500 sm:inline">{{ me.email }}</span>
            <button
              @click="signOut"
              class="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-100"
            >
              התנתקות
            </button>
          </template>
          <a
            v-else
            :href="loginUrl()"
            aria-label="התחברות עם Google"
            class="flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-neutral-700"
          >
            <span>התחברות עם</span>
            <img :src="googleG" alt="" class="h-4 w-auto shrink-0" />
          </a>
        </div>
      </div>
    </header>

    <div
      v-if="errorBanner"
      class="mx-auto mt-4 max-w-4xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 sm:mx-6 lg:mx-auto"
    >
      {{ errorBanner }}
    </div>

    <main class="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <router-view></router-view>
    </main>

    <FeedbackWidget v-if="me" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { loginUrl } from "@/api/client";
import { ensureMe, me, signOut as authSignOut } from "@/auth";
import FeedbackWidget from "@/components/FeedbackWidget.vue";
import logoMark from "@/assets/logo-mark.svg";
import googleG from "@/assets/google-g.svg";

const router = useRouter();
const errorBanner = ref("");

const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: "חשבון ה-Google הזה אינו רשום ל-NewsAgent. ניתן לפנות למנהל המערכת.",
  oauth_failed: "ההתחברות עם Google נכשלה. אפשר לנסות שוב.",
};

onMounted(async () => {
  const error = new URLSearchParams(window.location.search).get("error");
  // capacity_full gets its own dedicated screen in HomeView.vue (UX-DR5),
  // not the generic banner - showing both would be a redundant, weaker
  // version of the same message.
  if (error && error !== "capacity_full") {
    errorBanner.value = ERROR_MESSAGES[error] ?? "שגיאת התחברות.";
  }
  await ensureMe();
});

async function signOut() {
  await authSignOut();
  // The landing page is where a signed-out visitor belongs. Pushing to
  // /preferences here used to work only by bouncing off that route's guard.
  router.push("/");
}
</script>
