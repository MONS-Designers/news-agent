import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import HomeView from "../HomeView.vue";
import type { Me } from "@/api/client";

const getMyProfile = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, getMyProfile: (...args: unknown[]) => getMyProfile(...args) };
});

const ensureMe = vi.fn<() => Promise<Me | null>>();
vi.mock("@/auth", () => ({
  ensureMe: () => ensureMe(),
}));

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: HomeView },
      { path: "/preferences", component: { template: "<div>prefs</div>" } },
    ],
  });
}

async function mountHome(query: Record<string, string> = {}) {
  const router = makeRouter();
  await router.push({ path: "/", query });
  const wrapper = mount(HomeView, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

beforeEach(() => {
  getMyProfile.mockReset();
  ensureMe.mockReset();
  ensureMe.mockResolvedValue(null);
});

describe("HomeView - happy path", () => {
  it("shows the at-capacity screen and nothing else when ?error=capacity_full", async () => {
    const { wrapper } = await mountHome({ error: "capacity_full" });
    expect(wrapper.text()).toContain("אנחנו במלוא התפוסה כרגע");
    expect(wrapper.text()).not.toContain("הסיפור שלך"); // steps section not rendered
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("shows the default pitch copy for an anonymous visitor", async () => {
    ensureMe.mockResolvedValue(null);
    const { wrapper } = await mountHome();
    expect(wrapper.text()).toContain("דייג'סט אחד.");
    expect(wrapper.text()).not.toContain("אתה בפנים");
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("shows the default pitch copy for an admin-only identity (no user_id)", async () => {
    ensureMe.mockResolvedValue({ email: "admin@example.com", is_admin: true, user_id: null });
    const { wrapper } = await mountHome();
    expect(wrapper.text()).toContain("דייג'סט אחד.");
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("shows the first-run welcome copy for a user with no profile yet", async () => {
    ensureMe.mockResolvedValue({ email: "new@example.com", is_admin: false, user_id: 7 });
    getMyProfile.mockResolvedValue({
      field_name: null,
      role_name: null,
      experience_bucket: null,
      interest_free_text: null,
    });
    const { wrapper } = await mountHome();
    expect(wrapper.text()).toContain("אתה בפנים");
    expect(wrapper.text()).not.toContain("דייג'סט אחד.");
  });

  it("shows the default (non-first-run) copy for a returning user with a profile", async () => {
    ensureMe.mockResolvedValue({ email: "returning@example.com", is_admin: false, user_id: 8 });
    getMyProfile.mockResolvedValue({
      field_name: "פיתוח",
      role_name: "מפתח",
      experience_bucket: "3-5",
      interest_free_text: null,
    });
    const { wrapper } = await mountHome();
    expect(wrapper.text()).not.toContain("אתה בפנים");
    expect(wrapper.text()).toContain("דייג'סט אחד.");
  });

  it("navigates to /preferences when the CTA is clicked", async () => {
    const { wrapper, router } = await mountHome();
    await wrapper.find("button.cta").trigger("click");
    await flushPromises();
    expect(router.currentRoute.value.path).toBe("/preferences");
  });

  it("renders all 3 'how it works' step cards", async () => {
    const { wrapper } = await mountHome();
    expect(wrapper.findAll(".step-card")).toHaveLength(3);
    expect(wrapper.text()).toContain("הסיפור שלך");
    expect(wrapper.text()).toContain("הוא קורא הכל");
    expect(wrapper.text()).toContain("דייג'סט מסודר נוחת אצלך במייל");
  });
});

describe("HomeView - unhappy path / edge cases", () => {
  it("degrades to the default (non-first-run) copy, without error, when the profile fetch fails", async () => {
    ensureMe.mockResolvedValue({ email: "user@example.com", is_admin: false, user_id: 9 });
    getMyProfile.mockRejectedValue(new Error("network down"));
    const { wrapper } = await mountHome();

    expect(wrapper.text()).not.toContain("אתה בפנים");
    expect(wrapper.text()).toContain("דייג'סט אחד.");
  });

  it("mounts and unmounts cleanly (matchMedia/scroll/mousemove/IntersectionObserver listeners)", async () => {
    const { wrapper } = await mountHome();
    expect(() => wrapper.unmount()).not.toThrow();
  });

  it("treats any error value other than capacity_full as not-at-capacity", async () => {
    const { wrapper } = await mountHome({ error: "unauthorized" });
    expect(wrapper.text()).not.toContain("אנחנו במלוא התפוסה כרגע");
    expect(wrapper.text()).toContain("דייג'סט אחד.");
  });
});
