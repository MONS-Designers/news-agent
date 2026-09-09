// Shared auth state - single owner of "who is signed in" for the whole app.
// Views and the router guard read from here instead of fetching /auth/me themselves.
import { ref } from "vue";
import { getMe, logout, type Me } from "@/api/client";
import { clearProfileDraft } from "@/profile-draft";

export const me = ref<Me | null>(null);

let loaded = false;

export async function ensureMe(): Promise<Me | null> {
  if (!loaded) {
    me.value = await getMe();
    loaded = true;
  }
  return me.value;
}

export async function signOut(): Promise<void> {
  await logout();
  me.value = null;
  // Sign-out is a pure SPA navigation, no page reload - a second user signing
  // in in the same tab must not see the first user's cached profile draft.
  clearProfileDraft();
}
