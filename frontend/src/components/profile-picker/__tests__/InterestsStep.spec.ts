import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import InterestsStep from "../InterestsStep.vue";

const getMyProfile = vi.fn();
const getPromptSuggestions = vi.fn();
const updateMyProfile = vi.fn();
vi.mock("@/api/client", () => ({
  getMyProfile: (...args: unknown[]) => getMyProfile(...args),
  getPromptSuggestions: (...args: unknown[]) => getPromptSuggestions(...args),
  updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
}));

beforeEach(() => {
  getMyProfile.mockReset();
  getPromptSuggestions.mockReset();
  updateMyProfile.mockReset();
  getMyProfile.mockResolvedValue({
    field_name: "פיתוח",
    role_name: "מפתח",
    experience_bucket: "junior",
    interest_free_text: null,
  });
  getPromptSuggestions.mockResolvedValue([]);
});

function continueButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("button").find((b) => b.text() === "המשך")!;
}
function skipButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("button").find((b) => b.text().includes("מאוחר יותר"))!;
}

describe("InterestsStep - happy path", () => {
  it("prefills the textarea from the saved profile on mount", async () => {
    getMyProfile.mockResolvedValue({
      field_name: null,
      role_name: null,
      experience_bucket: null,
      interest_free_text: "בינה מלאכותית וטכנולוגיה",
    });
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

  it("saves trimmed, changed text and advances on success", async () => {
    updateMyProfile.mockResolvedValue({
      field_name: null,
      role_name: null,
      experience_bucket: null,
      interest_free_text: "טכנולוגיה",
    });
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    await wrapper.find("textarea").setValue("  טכנולוגיה  ");
    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(updateMyProfile).toHaveBeenCalledWith({ interestFreeText: "טכנולוגיה" });
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });
});

describe("InterestsStep - unhappy path / edge cases", () => {
  it("degrades to a blank textarea, without error, when the profile fetch fails", async () => {
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();

    expect((wrapper.find("textarea").element as HTMLTextAreaElement).value).toBe("");
    expect(wrapper.text()).not.toContain("נכשל");
  });

  it("degrades to no prompt suggestions, without error, when the prompt fetch fails", async () => {
    getPromptSuggestions.mockRejectedValue(new Error("llm down"));
    const wrapper = mount(InterestsStep, { props: { active: false } });
    await flushPromises();
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(wrapper.find('[role="group"]').exists()).toBe(false);
    expect(wrapper.text()).not.toContain("נכשל");
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
      field_name: null,
      role_name: null,
      experience_bucket: null,
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
      field_name: null,
      role_name: null,
      experience_bucket: null,
      interest_free_text: "טכנולוגיה חדשה",
    });
    await flushPromises();

    expect(updateMyProfile).toHaveBeenCalledTimes(1);
  });
});
