<template>
  <div class="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
    <header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-4xl items-center gap-8 px-4 py-3 sm:px-6">
        <span class="text-lg font-semibold tracking-tight">NewsAgent</span>
        <nav class="flex gap-1">
          <router-link
            v-if="me?.is_admin"
            to="/admin"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            Admin
          </router-link>
          <router-link
            to="/preferences"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            Preferences
          </router-link>
        </nav>
        <div class="ms-auto flex items-center gap-3">
          <template v-if="me">
            <span class="hidden text-sm text-neutral-500 sm:inline">{{ me.email }}</span>
            <button
              @click="signOut"
              class="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm font-medium text-neutral-700 transition-colors hover:bg-neutral-100"
            >
              Sign out
            </button>
          </template>
          <a
            v-else
            :href="loginUrl()"
            class="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-neutral-700"
          >
            Sign in with Google
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
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { loginUrl } from "@/api/client";
import { ensureMe, me, signOut as authSignOut } from "@/auth";

const router = useRouter();
const errorBanner = ref("");

const ERROR_MESSAGES: Record<string, string> = {
  unauthorized: "This Google account is not registered for NewsAgent. Contact an admin.",
  oauth_failed: "Google sign-in failed. Please try again.",
};

onMounted(async () => {
  const error = new URLSearchParams(window.location.search).get("error");
  if (error) {
    errorBanner.value = ERROR_MESSAGES[error] ?? "Sign-in error.";
  }
  await ensureMe();
});

async function signOut() {
  await authSignOut();
  router.push("/preferences");
}
</script>
