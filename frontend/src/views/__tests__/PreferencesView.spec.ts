import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PreferencesView from "../PreferencesView.vue";
import { ApiError } from "@/api/client";
import { profileDraft, preferencesDraft } from "@/profile-draft";

const listMyPreferences = vi.fn();
const getMyProfile = vi.fn();
const getMySubscription = vi.fn();
const updateMySubscription = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listMyPreferences: (...args: unknown[]) => listMyPreferences(...args),
    getMyProfile: (...args: unknown[]) => getMyProfile(...args),
    getMySubscription: (...args: unknown[]) => getMySubscription(...args),
    updateMySubscription: (...args: unknown[]) => updateMySubscription(...args),
  };
});

const ProfilePickerShellStub = {
  props: ["canExit"],
  emits: ["topics-saved", "back"],
  template: `<div>
    <button class="stub-shell-saved" @click="$emit('topics-saved')">shell</button>
    <button class="stub-shell-back" :data-can-exit="canExit" @click="$emit('back')">back</button>
  </div>`,
};

const PREFS = [
  { topic_id: 1, name: "AI", subscribed: true },
  { topic_id: 2, name: "Security", subscribed: false },
];
const RETURNING_PROFILE = {
  field_name: "פיתוח",
  role_name: "מפתח",
  experience_bucket: "3-5",
  interest_free_text: "בינה מלאכותית",
};
const NEW_PROFILE = {
  field_name: null,
  role_name: null,
  experience_bucket: null,
  interest_free_text: null,
};

function mountView() {
  return mount(PreferencesView, {
    global: { stubs: { ProfilePickerShell: ProfilePickerShellStub } },
  });
}

beforeEach(() => {
  // profileDraft/preferencesDraft are module-level singletons (survive SPA
  // navigation by design - see loadPreferences()'s `alreadyKnown` check) -
  // reset between tests so one test populating the store doesn't change
  // whether the next test's mount starts in the "already known" state.
  profileDraft.value = null;
  preferencesDraft.value = [];
  listMyPreferences.mockReset();
  getMyProfile.mockReset();
  getMySubscription.mockReset();
  updateMySubscription.mockReset();
  listMyPreferences.mockResolvedValue(PREFS);
  getMySubscription.mockResolvedValue({ unsubscribed: false });
});

describe("PreferencesView - happy path", () => {
  it("shows a spinner beside the loading text before the initial fetch resolves, with neither summary nor wizard rendered underneath it", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();

    expect(wrapper.text()).toContain("טעינה…");
    expect(wrapper.find("svg").exists()).toBe(true);
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("פיתוח");

    await flushPromises();
    expect(wrapper.text()).not.toContain("טעינה…");
  });

  it("seeds the shared profile-draft store (initProfileDraft) with the fetched profile and preferences", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    mountView();
    await flushPromises();

    expect(profileDraft.value).toEqual(RETURNING_PROFILE);
    expect(preferencesDraft.value).toEqual(PREFS);
  });

  it("shows the summary instantly with no loading flash on a revisit (profileDraft already populated from an earlier mount in this tab)", async () => {
    // Simulates navigating away (e.g. to Home) and back within the same SPA
    // session, without a full page reload - profileDraft survives that.
    profileDraft.value = { ...RETURNING_PROFILE, topics_stale_at: null };
    preferencesDraft.value = [...PREFS];
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);

    const wrapper = mountView();
    // No await flushPromises() first - checking the very first synchronous
    // render, before the background revalidation fetch has any chance to
    // resolve, is the whole point.
    expect(wrapper.text()).not.toContain("טעינה…");
    expect(wrapper.text()).toContain("פיתוח");
  });

  it("shows the returning-user summary with subscribed topics and profile fields", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("פיתוח");
    expect(wrapper.text()).toContain("מפתח");
    expect(wrapper.text()).toContain("3–5 שנים");
    expect(wrapper.text()).toContain("בינה מלאכותית");
    expect(wrapper.text()).toContain("AI");
    expect(wrapper.text()).not.toContain("Security");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
  });

  it("shows 'עדיין אין' when the user has no subscribed topics", async () => {
    listMyPreferences.mockResolvedValue([{ topic_id: 2, name: "Security", subscribed: false }]);
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("עדיין אין");
  });

  it("switches to the profile wizard when 'עריכת פרופיל' is clicked", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    const editButton = wrapper.findAll("button").find((b) => b.text() === "עריכת פרופיל")!;
    await editButton.trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("עריכת פרופיל");
  });

  it("shows the profile wizard directly for a brand-new user (no field_name yet)", async () => {
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("טוען");
  });

  it("wraps the summary and subscription row in HybridDepthBackground's void/orb chrome", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mount(PreferencesView, {
      global: { stubs: { ProfilePickerShell: ProfilePickerShellStub } },
    });
    await flushPromises();

    // HybridDepthBackground is not stubbed - its orb/grain aria-hidden
    // markup renders for real, proving the summary is wrapped by it (rather
    // than sitting in the old plain-Tailwind container).
    expect(wrapper.findAll('[aria-hidden="true"]').length).toBeGreaterThanOrEqual(2);
  });

  it("renders the topics-stale warning with the alert-frame treatment, not the old amber Tailwind banner", async () => {
    getMyProfile.mockResolvedValue({ ...RETURNING_PROFILE, topics_stale_at: "2026-09-01T00:00:00Z" });
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("שינית את הפרופיל");
    expect(wrapper.find(".bg-amber-50").exists()).toBe(false);
    expect(wrapper.find(".border-amber-300").exists()).toBe(false);
    expect(wrapper.find('[class*="border-hd-accent-2/40"]').exists()).toBe(true);
  });

  it("renders subscribed topics as read-only pills - no '✕' and no click handler", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    const pill = wrapper.findAll("span").find((s) => s.text() === "AI")!;
    expect(pill.text()).not.toContain("✕");
    // A read-only pill is a <span>, not a <button> - there is nothing to click.
    expect(pill.element.tagName).toBe("SPAN");
  });

  it("toggles the subscription pause/resume label and calls the API with the flipped value", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    updateMySubscription.mockResolvedValue({ unsubscribed: true });
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("פעיל");
    const toggleButton = wrapper.findAll("button").find((b) => b.text() === "השהיה")!;
    await toggleButton.trigger("click");
    await flushPromises();

    expect(updateMySubscription).toHaveBeenCalledWith(true);
    expect(wrapper.text()).toContain("מושהה");
  });

  it("swaps the single page heading between the summary and the wizard instead of stacking two", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("העדפות הנושאים שלי");
    expect(wrapper.text()).not.toContain("הגדרת הפרופיל שלך");

    await wrapper.findAll("button").find((b) => b.text() === "עריכת פרופיל")!.trigger("click");
    expect(wrapper.text()).toContain("הגדרת הפרופיל שלך");
    expect(wrapper.text()).not.toContain("העדפות הנושאים שלי");
  });

  it("keeps the page heading (not the wizard's) while the first fetch is still in flight", async () => {
    // showSummary is false until a profile with a field_name arrives, so
    // without gating on `loading` the title would read as the wizard's for
    // the split second before the fetch resolves.
    getMyProfile.mockReturnValue(new Promise(() => {}));
    const wrapper = mountView();
    expect(wrapper.text()).toContain("טעינה…");
    expect(wrapper.text()).toContain("העדפות הנושאים שלי");
    expect(wrapper.text()).not.toContain("הגדרת הפרופיל שלך");
  });

  it("returns a returning user to the read-only summary when the wizard steps back off its first step", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    await wrapper.findAll("button").find((b) => b.text() === "עריכת פרופיל")!.trigger("click");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);

    await wrapper.find(".stub-shell-back").trigger("click");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
    expect(wrapper.text()).toContain("עריכת פרופיל");
  });

  it("tells the wizard it may be exited when a saved profile sits behind it", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    await wrapper.findAll("button").find((b) => b.text() === "עריכת פרופיל")!.trigger("click");
    expect(wrapper.find(".stub-shell-back").attributes("data-can-exit")).toBe("true");
  });

  it("tells the wizard it may not be exited for a new user - there is no summary behind it yet", async () => {
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
    expect(wrapper.find(".stub-shell-back").attributes("data-can-exit")).toBe("false");
  });

  it("refreshes preferences quietly (without a loading flicker) after the wizard reports topics-saved", async () => {
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    expect(listMyPreferences).toHaveBeenCalledTimes(1);

    listMyPreferences.mockResolvedValue([{ topic_id: 3, name: "Cloud", subscribed: true }]);
    await wrapper.find(".stub-shell-saved").trigger("click");
    await flushPromises();

    expect(listMyPreferences).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain("טוען");
  });
});

describe("PreferencesView - unhappy path / edge cases", () => {
  it("shows a sign-in message on a 401, with no wizard rendered underneath it", async () => {
    getMyProfile.mockRejectedValue(new ApiError(401, "unauthorized"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("התחבר עם Google");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
  });

  it("shows a no-profile message on a 403, with no wizard rendered underneath it", async () => {
    getMyProfile.mockRejectedValue(new ApiError(403, "forbidden"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("אין פרופיל משתמש");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
  });

  it("shows a generic error message on any other load failure, with no wizard rendered underneath it", async () => {
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת ההעדפות נכשלה");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
  });

  it("no longer renders the profile wizard underneath the error banner (fixed - one loading/error/summary/wizard v-if chain now gates all four)", async () => {
    // Before the original fix: showSummary requires a loaded profile with
    // field_name, and on any load failure profile.value stays null, so a
    // second, independent v-if/v-else block (subscription box vs.
    // ProfilePickerShell) picked its v-else branch and rendered the wizard
    // alongside the error message. That second chain was later merged into
    // the single loading/error/summary/wizard chain above (GH #79 item 3),
    // so ProfilePickerShell only ever renders via the chain's own v-else.
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("טעינת ההעדפות נכשלה");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(false);
  });

  it("keeps a new user in the wizard when Step 1 saves, instead of swapping in the summary mid-onboarding", async () => {
    // Step 1 patches the draft with the field_name it just wrote, so a
    // showSummary derived from the stored profile alone would flip true
    // between Step 1 and Step 2 and yank the wizard out from under the user.
    // Caught by the Playwright onboarding spec before this guard existed.
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);

    profileDraft.value = { ...profileDraft.value!, field_name: "פיתוח", role_name: "מפתח" };
    await flushPromises();

    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
    expect(wrapper.text()).toContain("הגדרת הפרופיל שלך");
    expect(wrapper.text()).not.toContain("עריכת פרופיל");
  });

  it("after first completing the wizard as a new user, does not switch to the summary view", async () => {
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    await wrapper.find(".stub-shell-saved").trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
    expect(wrapper.text()).not.toContain("עריכת פרופיל");
  });

  it("leaves the subscription state unchanged and re-enables the toggle when updateMySubscription fails", async () => {
    getMyProfile.mockResolvedValue(RETURNING_PROFILE);
    updateMySubscription.mockRejectedValue(new Error("boom"));
    const wrapper = mountView();
    await flushPromises();

    const toggleButton = wrapper.findAll("button").find((b) => b.text() === "השהיה")!;
    await toggleButton.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("פעיל"); // unchanged, not "מושהה"
    expect(toggleButton.attributes("disabled")).toBeUndefined(); // re-enabled for retry
  });

  it("silently ignores a failed quiet refresh without showing an error", async () => {
    getMyProfile.mockResolvedValue(NEW_PROFILE);
    const wrapper = mountView();
    await flushPromises();

    listMyPreferences.mockRejectedValue(new Error("network down"));
    await wrapper.find(".stub-shell-saved").trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("נכשל");
  });

  it("falls back to the raw bucket string for an unrecognized experience_bucket value", async () => {
    getMyProfile.mockResolvedValue({ ...RETURNING_PROFILE, experience_bucket: "50+" });
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("50+");
  });

  it("shows a dash for a missing experience_bucket", async () => {
    getMyProfile.mockResolvedValue({ ...RETURNING_PROFILE, experience_bucket: null });
    const wrapper = mountView();
    await flushPromises();
    const dd = wrapper.findAll("dd").find((d) => d.text() === "-");
    expect(dd).toBeTruthy();
  });
});
