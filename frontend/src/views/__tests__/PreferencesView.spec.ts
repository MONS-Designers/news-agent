import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import PreferencesView from "../PreferencesView.vue";
import { ApiError } from "@/api/client";

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
  emits: ["topics-saved"],
  template: `<button class="stub-shell-saved" @click="$emit('topics-saved')">shell</button>`,
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
  listMyPreferences.mockReset();
  getMyProfile.mockReset();
  getMySubscription.mockReset();
  updateMySubscription.mockReset();
  listMyPreferences.mockResolvedValue(PREFS);
  getMySubscription.mockResolvedValue({ unsubscribed: false });
});

describe("PreferencesView - happy path", () => {
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
  it("shows a sign-in message on a 401", async () => {
    getMyProfile.mockRejectedValue(new ApiError(401, "unauthorized"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("התחבר עם Google");
  });

  it("shows a no-profile message on a 403", async () => {
    getMyProfile.mockRejectedValue(new ApiError(403, "forbidden"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("אין פרופיל משתמש");
  });

  it("shows a generic error message on any other load failure", async () => {
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mountView();
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת ההעדפות נכשלה");
  });

  it("documents current behavior: the profile wizard also renders underneath an error banner, since showSummary is false whenever profile failed to load", async () => {
    // showSummary requires a loaded profile with field_name - on any load
    // failure profile.value stays null, so the template's second, independent
    // v-if/v-else block (subscription box vs. ProfilePickerShell) still picks
    // its v-else branch and renders the wizard alongside the error message.
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mountView();
    await flushPromises();

    expect(wrapper.text()).toContain("טעינת ההעדפות נכשלה");
    expect(wrapper.find(".stub-shell-saved").exists()).toBe(true);
  });

  it("after first completing the wizard as a new user, does not switch to the summary view - profile is never re-fetched, only preferences", async () => {
    // refreshPreferencesQuietly() only re-syncs `preferences`, not `profile`
    // itself, so profile.value.field_name stays null client-side even though
    // AboutYouStep already saved the real field_name server-side - the view
    // stays on the wizard until a full reload re-fetches the profile.
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
