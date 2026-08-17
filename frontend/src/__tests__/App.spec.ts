import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import App from "@/App.vue";
import { me, ensureMe, signOut } from "@/auth";

// The factory can't close over a module-scope const here (vi.mock is
// hoisted above this file's own imports, so any outer `const` would still
// be in its temporal dead zone the first time the factory actually runs,
// which happens while App.vue itself is being imported below). Building the
// ref inside the factory via a dynamic import sidesteps that; the `me`
// import above resolves to this same mocked instance once the module
// system settles, which is late enough for test bodies to use freely.
vi.mock("@/auth", async () => {
  const { ref } = await import("vue");
  return {
    me: ref(null),
    ensureMe: vi.fn(async () => null),
    signOut: vi.fn(async () => {}),
  };
});

const Blank = { template: "<div>page</div>" };

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: Blank },
      { path: "/preferences", component: Blank },
      { path: "/admin", component: Blank },
      { path: "/admin/taxonomy", component: Blank },
      { path: "/admin/engagement", component: Blank },
    ],
  });
}

async function mountApp() {
  const router = makeRouter();
  await router.push("/");
  const wrapper = mount(App, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

beforeEach(() => {
  me.value = null;
  vi.mocked(ensureMe).mockClear();
  vi.mocked(signOut).mockClear();
  window.history.pushState({}, "", "/");
});
afterEach(() => {
  window.history.pushState({}, "", "/");
});

describe("App - happy path", () => {
  it("shows a Google login link and no admin nav for an anonymous visitor", async () => {
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("התחברות עם Google");
    expect(wrapper.text()).not.toContain("ניהול");
    expect(wrapper.text()).not.toContain("התנתקות");
  });

  it("shows the user's email and a sign-out button when signed in", async () => {
    me.value = { email: "user@example.com", is_admin: false, user_id: 3 };
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("user@example.com");
    expect(wrapper.text()).toContain("התנתקות");
    expect(wrapper.text()).not.toContain("התחברות עם Google");
  });

  it("shows admin nav links only for an admin", async () => {
    me.value = { email: "admin@example.com", is_admin: true, user_id: 1 };
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("ניהול");
    expect(wrapper.text()).toContain("טקסונומיה");
    expect(wrapper.text()).toContain("מעורבות");
  });

  it("hides admin nav links for a signed-in non-admin", async () => {
    me.value = { email: "user@example.com", is_admin: false, user_id: 3 };
    const { wrapper } = await mountApp();
    expect(wrapper.text()).not.toContain("ניהול");
    expect(wrapper.text()).not.toContain("טקסונומיה");
    expect(wrapper.text()).not.toContain("מעורבות");
  });

  it("always shows the Preferences nav link regardless of sign-in state", async () => {
    const { wrapper: anon } = await mountApp();
    expect(anon.text()).toContain("העדפות");

    me.value = { email: "user@example.com", is_admin: false, user_id: 3 };
    const { wrapper: signedIn } = await mountApp();
    expect(signedIn.text()).toContain("העדפות");
  });

  it("signs out and navigates to /preferences", async () => {
    me.value = { email: "user@example.com", is_admin: false, user_id: 3 };
    const { wrapper, router } = await mountApp();

    const signOutButton = wrapper.findAll("button").find((b) => b.text() === "התנתקות")!;
    await signOutButton.trigger("click");
    await flushPromises();

    expect(signOut).toHaveBeenCalled();
    expect(router.currentRoute.value.path).toBe("/preferences");
  });
});

describe("App - unhappy path / edge cases", () => {
  it("shows the unauthorized-account banner for ?error=unauthorized", async () => {
    window.history.pushState({}, "", "/?error=unauthorized");
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("אינו רשום ל-NewsAgent");
  });

  it("shows the OAuth-failed banner for ?error=oauth_failed", async () => {
    window.history.pushState({}, "", "/?error=oauth_failed");
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("ההתחברות עם Google נכשלה");
  });

  it("falls back to a generic login-error banner for an unrecognized error code", async () => {
    window.history.pushState({}, "", "/?error=something_else");
    const { wrapper } = await mountApp();
    expect(wrapper.text()).toContain("שגיאת התחברות");
  });

  it("shows no banner at all for ?error=capacity_full - HomeView owns that screen", async () => {
    window.history.pushState({}, "", "/?error=capacity_full");
    const { wrapper } = await mountApp();
    expect(wrapper.text()).not.toContain("שגיאת התחברות");
    expect(wrapper.text()).not.toContain("אינו רשום ל-NewsAgent");
  });

  it("shows no banner when there is no error query param", async () => {
    const { wrapper } = await mountApp();
    expect(wrapper.find(".border-red-200").exists()).toBe(false);
  });

  it("calls ensureMe on mount regardless of error banner state", async () => {
    window.history.pushState({}, "", "/?error=unauthorized");
    await mountApp();
    expect(ensureMe).toHaveBeenCalledTimes(1);
  });
});
