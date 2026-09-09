import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import InterestsStep from "../InterestsStep.vue";
import { profileDraft } from "@/profile-draft";

const getPromptSuggestions = vi.fn();
const updateMyProfile = vi.fn();
vi.mock("@/api/client", () => ({
  getPromptSuggestions: (...args: unknown[]) => getPromptSuggestions(...args),
  updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
}));

const BASE_PROFILE = {
  field_name: "פיתוח",
  role_name: "מפתח",
  experience_bucket: "junior",
  interest_free_text: null as string | null,
  topics_stale_at: null,
};

beforeEach(() => {
  getPromptSuggestions.mockReset();
  updateMyProfile.mockReset();
  profileDraft.value = { ...BASE_PROFILE };
  getPromptSuggestions.mockResolvedValue([]);
});

function continueButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("button").find((b) => b.text() === "המשך")!;
}
function skipButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("button").find((b) => b.text().includes("מאוחר יותר"))!;
}

describe("InterestsStep - happy path", () => {
  it("prefills the textarea from profileDraft on mount", async () => {
    profileDraft.value = { ...BASE_PROFILE, interest_free_text: "בינה מלאכותית וטכנולוגיה" };
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe(
      "בינה מלאכותית וטכנולוגיה",
    );
  });

  it("fetches up to 3 prompt suggestions once the step becomes active", async () => {
    getPromptSuggestions.mockResolvedValue(["רעיון א", "רעיון ב", "רעיון ג", "רעיון ד"]);
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    expect(getPromptSuggestions).not.toHaveBeenCalled();

    await wrapper.setProps({ active: true });
    await flushPromises();

    const prompts = wrapper.findAll('[role="group"] button');
    expect(prompts).toHaveLength(3);
  });

  it("shows the HybridSpinner loading placeholder while prompts are genuinely re-fetching, then swaps to the chips", async () => {
    let resolvePrompts: (v: string[]) => void = () => {};
    getPromptSuggestions.mockReturnValue(new Promise((resolve) => (resolvePrompts = resolve)));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(wrapper.text()).toContain("טעינת הצעות…");
    expect(wrapper.find("svg").exists()).toBe(true);
    expect(wrapper.find('[role="group"]').exists()).toBe(false);

    resolvePrompts(["רעיון א"]);
    await flushPromises();

    expect(wrapper.text()).not.toContain("טעינת הצעות…");
    expect(wrapper.findAll('[role="group"] button')).toHaveLength(1);
  });

  it("keeps existing prompt chips across a re-entry when Field/Role/Experience are unchanged (no flicker, no re-fetch, no loading placeholder)", async () => {
    getPromptSuggestions.mockResolvedValue(["רעיון א", "רעיון ב"]);
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.setProps({ active: true });
    await flushPromises();
    expect(getPromptSuggestions).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll('[role="group"] button')).toHaveLength(2);

    // Leave and return to Step 2 with the identical saved profile.
    await wrapper.setProps({ active: false });
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(getPromptSuggestions).toHaveBeenCalledTimes(1); // not re-fetched
    expect(wrapper.findAll('[role="group"] button')).toHaveLength(2); // chips never cleared
    expect(wrapper.text()).not.toContain("טעינת הצעות…");
  });

  it("re-fetches prompt suggestions when Field/Role changed since the last fetch (seen via the shared profileDraft, no plumbing)", async () => {
    getPromptSuggestions
      .mockResolvedValueOnce(["רעיון א"])
      .mockResolvedValueOnce(["רעיון חדש"]);
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.setProps({ active: true });
    await flushPromises();
    expect(wrapper.text()).toContain("רעיון א");

    // Simulates AboutYouStep patching the shared store mid-session.
    profileDraft.value = { ...BASE_PROFILE, field_name: "עיצוב", role_name: "מעצב" };
    await wrapper.setProps({ active: false });
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(getPromptSuggestions).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("רעיון חדש");
    expect(wrapper.text()).not.toContain("רעיון א");
  });

  it("clicking a prompt suggestion fills the textarea", async () => {
    getPromptSuggestions.mockResolvedValue(["חדשות בינה מלאכותית"]);
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    await wrapper.setProps({ active: true });
    await flushPromises();

    await wrapper.find('[role="group"] button').trigger("click");
    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe(
      "חדשות בינה מלאכותית",
    );
  });

  it("Continue and Skip both advance immediately with no API call when the text is unchanged", async () => {
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await continueButton(wrapper).trigger("click");
    await flushPromises();
    expect(updateMyProfile).not.toHaveBeenCalled();
    expect(wrapper.emitted("continue")).toHaveLength(1);

    await skipButton(wrapper).trigger("click");
    await flushPromises();
    expect(updateMyProfile).not.toHaveBeenCalled();
    expect(wrapper.emitted("continue")).toHaveLength(2);
  });

  it("saves trimmed, changed text, patches profileDraft, and advances on success", async () => {
    updateMyProfile.mockResolvedValue({
      ...BASE_PROFILE,
      interest_free_text: "טכנולוגיה",
    });
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.find("textarea").setValue("  טכנולוגיה  ");
    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(updateMyProfile).toHaveBeenCalledWith({ interestFreeText: "טכנולוגיה" });
    expect(profileDraft.value?.interest_free_text).toBe("טכנולוגיה");
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });
});

describe("InterestsStep - unhappy path / edge cases", () => {
  it("degrades to a blank textarea, without error, when profileDraft was never seeded", async () => {
    profileDraft.value = null;
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe("");
    expect(wrapper.text()).not.toContain("נכשל");
  });

  it("degrades to no prompt suggestions, without error, and hides the loading placeholder, when the prompt fetch fails", async () => {
    getPromptSuggestions.mockRejectedValue(new Error("llm down"));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(wrapper.find('[role="group"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain("נכשל");
    expect(wrapper.text()).not.toContain("טעינת הצעות…");
  });

  it("does not re-fetch or gate anything when profileDraft is null while the step becomes active", async () => {
    profileDraft.value = null;
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(getPromptSuggestions).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("טעינת הצעות…");
  });

  it("shows a save error and does not advance when updateMyProfile fails", async () => {
    updateMyProfile.mockRejectedValue(new Error("boom"));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.find("textarea").setValue("טכנולוגיה חדשה");
    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("השמירה נכשלה");
    expect(wrapper.emitted("continue")).toBeFalsy();
  });

  it("allows retrying after a failed save (saving flag resets)", async () => {
    updateMyProfile.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce({
      ...BASE_PROFILE,
      interest_free_text: "טכנולוגיה חדשה",
    });
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    await wrapper.find("textarea").setValue("טכנולוגיה חדשה");

    await continueButton(wrapper).trigger("click");
    await flushPromises();
    expect(wrapper.emitted("continue")).toBeFalsy();

    await continueButton(wrapper).trigger("click");
    await flushPromises();
    expect(updateMyProfile).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });

  it("treats whitespace-only text as unchanged and skips the API call", async () => {
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.find("textarea").setValue("     ");
    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(updateMyProfile).not.toHaveBeenCalled();
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });

  it("does not fire a second save while one is already in flight (double-click guard)", async () => {
    let resolveSave: (v: unknown) => void = () => {};
    updateMyProfile.mockReturnValue(new Promise((resolve) => (resolveSave = resolve)));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.find("textarea").setValue("טכנולוגיה חדשה");
    const btn = continueButton(wrapper);
    await btn.trigger("click");
    await btn.trigger("click");
    resolveSave({
      ...BASE_PROFILE,
      interest_free_text: "טכנולוגיה חדשה",
    });
    await flushPromises();

    expect(updateMyProfile).toHaveBeenCalledTimes(1);
  });
});
