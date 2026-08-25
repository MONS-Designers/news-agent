<template>
  <div class="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
    <header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-4xl items-center gap-8 px-4 py-3 sm:px-6">
        <router-link
          to="/"
          dir="ltr"
          class="-mx-2 -my-1 flex items-center gap-2 rounded-lg px-2 py-1 text-lg font-semibold tracking-tight transition-all duration-300 ease-out hover:shadow-[0_6px_20px_-4px_rgba(240,180,41,0.5)]"
        >
          <img :src="logoMark" alt="" class="h-7 w-7 rounded-lg" />
          <span>News<span class="text-amber-500">Agent</span></span>
        </router-link>
        <nav class="flex gap-1">
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
            <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true" class="shrink-0">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" />
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z" />
              <path fill="#FBBC05" d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71s.102-1.17.282-1.71V4.958H.957C.348 6.173 0 7.548 0 9s.348 2.827.957 4.042l3.007-2.332z" />
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" />
            </svg>
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
  router.push("/preferences");
}
</script>
