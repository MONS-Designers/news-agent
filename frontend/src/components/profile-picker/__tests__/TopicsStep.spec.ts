import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import TopicsStep from "../TopicsStep.vue";

const push = vi.fn();
vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));

const getTopicSuggestions = vi.fn();
const listMyPreferences = vi.fn();
const updateMyPreferences = vi.fn();
vi.mock("@/api/client", () => ({
  getTopicSuggestions: (...args: unknown[]) => getTopicSuggestions(...args),
  listMyPreferences: (...args: unknown[]) => listMyPreferences(...args),
  updateMyPreferences: (...args: unknown[]) => updateMyPreferences(...args),
}));

const PREFS = [
  { topic_id: 1, name: "AI", subscribed: true },
  { topic_id: 2, name: "Security", subscribed: false },
  { topic_id: 3, name: "Cloud", subscribed: true },
  { topic_id: 4, name: "Mobile", subscribed: false },
  { topic_id: 5, name: "Data", subscribed: false },
];

function mountStep() {
  return mount(TopicsStep, { props: { active: true } });
}

beforeEach(() => {
  push.mockClear();
  getTopicSuggestions.mockReset();
  listMyPreferences.mockReset();
  updateMyPreferences.mockReset();
  listMyPreferences.mockResolvedValue(PREFS);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("TopicsStep - happy path", () => {
  it("renders every suggestion but pre-picks only the real topics", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1, 2, 3],
      suggested_new_topic_names: ["Robotics"],
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(4);
    const pressed = buttons.filter((b) => b.attributes("aria-pressed") === "true");
    expect(pressed).toHaveLength(3);
    expect(buttons[3].text()).toContain("Robotics");
    expect(buttons[3].attributes("aria-pressed")).toBe("false");
  });

  it("never auto-picks an invented topic, even when real ones don't fill the cap", async () => {
    // An invented name is created as a pending Topic with no RSS sources
    // behind it, so auto-subscribing burns one of only MAX_TOPICS slots on a
    // topic that yields zero articles - reported by a beta reader who was
    // silently signed up to two topics they never chose.
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1],
      suggested_new_topic_names: ["Autism research", "Autism education"],
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(3);
    const pressed = buttons.filter((b) => b.attributes("aria-pressed") === "true");
    expect(pressed).toHaveLength(1);
    expect(pressed[0].text()).toContain("AI");
  });

  it("filters out a suggested topic id that doesn't resolve locally (stale id)", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1, 999],
      suggested_new_topic_names: [],
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0].text()).toContain("AI");
  });

  it("toggles a chip on and off", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1],
      suggested_new_topic_names: [],
    });
    const wrapper = mountStep();
    await flushPromises();

    const chip = wrapper.find('[role="group"] button');
    expect(chip.attributes("aria-pressed")).toBe("true");
    await chip.trigger("click");
    expect(chip.attributes("aria-pressed")).toBe("false");
    await chip.trigger("click");
    expect(chip.attributes("aria-pressed")).toBe("true");
  });

  it("saves picked topics and navigates home on success", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1, 2],
      suggested_new_topic_names: ["Robotics"],
    });
    updateMyPreferences.mockResolvedValue(PREFS);
    const wrapper = mountStep();
    await flushPromises();

    // Robotics is on screen but unpicked, so it must not reach the save.
    const saveButton = wrapper.findAll("button").find((b) => b.text().includes("אני רוצה לקבל"))!;
    await saveButton.trigger("click");
    await flushPromises();

    expect(updateMyPreferences).toHaveBeenCalledWith([1, 2], []);
    expect(wrapper.emitted("saved")).toBeTruthy();
    expect(push).toHaveBeenCalledWith("/");
  });
});

describe("TopicsStep - unhappy path / edge cases", () => {
  it("shows a load error and disables Save when both calls fail", async () => {
    getTopicSuggestions.mockRejectedValue(new Error("network down"));
    listMyPreferences.mockRejectedValue(new Error("network down"));
    const wrapper = mountStep();
    await flushPromises();

    expect(wrapper.text()).toContain("טעינת הנושאים נכשלה");
    const saveButton = wrapper.findAll("button").find((b) => b.attributes("disabled") !== undefined);
    expect(saveButton).toBeTruthy();
  });

  it("falls back to current subscriptions (subscribed-first) when suggestions come back failed", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "failed",
      suggested_topic_ids: null,
      suggested_new_topic_names: null,
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    // 2 subscribed + 3 unsubscribed = 5 total chips rendered, first 2 (subscribed) pre-picked
    expect(buttons).toHaveLength(5);
    const pressed = buttons.filter((b) => b.attributes("aria-pressed") === "true");
    expect(pressed).toHaveLength(2);
    expect(pressed.map((b) => b.text())).toEqual(
      expect.arrayContaining([expect.stringContaining("AI"), expect.stringContaining("Cloud")]),
    );
  });

  it("falls back to current subscriptions when status is ready but the chip list is empty", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [],
      suggested_new_topic_names: [],
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(5);
  });

  it("falls back to all topics (no subscriptions to prefer) when nothing is subscribed", async () => {
    listMyPreferences.mockResolvedValue(PREFS.map((p) => ({ ...p, subscribed: false })));
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "failed",
      suggested_topic_ids: null,
      suggested_new_topic_names: null,
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    const pressed = buttons.filter((b) => b.attributes("aria-pressed") === "true");
    expect(pressed).toHaveLength(4); // MAX_TOPICS
  });

  it("shows extended-wait copy on pending_slow, then resolves once ready", async () => {
    vi.useFakeTimers();
    getTopicSuggestions
      .mockResolvedValueOnce({ suggestion_status: "pending_slow", suggested_topic_ids: null, suggested_new_topic_names: null })
      .mockResolvedValueOnce({ suggestion_status: "ready", suggested_topic_ids: [1], suggested_new_topic_names: [] });

    const wrapper = mountStep();
    await flushPromises();

    expect(wrapper.text()).toContain("עדיין מנסים");

    await vi.advanceTimersByTimeAsync(400);
    await flushPromises();

    expect(wrapper.text()).not.toContain("עדיין מנסים");
    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(1);
  }, 15000);

  it("exhausts the poll budget and falls back to current subscriptions instead of loading forever", async () => {
    vi.useFakeTimers();
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "pending",
      suggested_topic_ids: null,
      suggested_new_topic_names: null,
    });

    const wrapper = mountStep();
    await flushPromises();

    // 112 attempts * 400ms poll interval, plus slack.
    await vi.advanceTimersByTimeAsync(112 * 400 + 1000);
    await flushPromises();

    expect(wrapper.text()).not.toContain("מוצא הצעות בשבילך");
    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(5);
  }, 20000);

  it("shows a save error and does not navigate when updateMyPreferences fails", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1],
      suggested_new_topic_names: [],
    });
    updateMyPreferences.mockRejectedValue(new Error("boom"));
    const wrapper = mountStep();
    await flushPromises();

    const saveButton = wrapper.findAll("button").find((b) => b.text().includes("אני רוצה לקבל"))!;
    await saveButton.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("שמירת ההעדפות נכשלה");
    expect(push).not.toHaveBeenCalled();
    expect(wrapper.emitted("saved")).toBeFalsy();
  });

  it("shows a cap hint instead of picking a 5th topic, and clears it after a timeout", async () => {
    vi.useFakeTimers();
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1, 2, 3, 4, 5],
      suggested_new_topic_names: [],
    });
    const wrapper = mountStep();
    await flushPromises();

    const buttons = wrapper.findAll('[role="group"] button');
    expect(buttons).toHaveLength(5);
    const unpicked = buttons.find((b) => b.attributes("aria-pressed") === "false")!;
    await unpicked.trigger("click");

    expect(wrapper.text()).toContain("הגעת ל-4");
    expect(unpicked.attributes("aria-pressed")).toBe("false");

    await vi.advanceTimersByTimeAsync(2500);
    await flushPromises();
    expect(wrapper.text()).not.toContain("הגעת ל-4");
  });

  it("does not reload when active flips false then true again after the first load", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1],
      suggested_new_topic_names: [],
    });
    const wrapper = mount(TopicsStep, { props: { active: true } });
    await flushPromises();
    expect(getTopicSuggestions).toHaveBeenCalledTimes(1);

    await wrapper.setProps({ active: false });
    await wrapper.setProps({ active: true });
    await flushPromises();

    expect(getTopicSuggestions).toHaveBeenCalledTimes(1);
  });

  it("does not fire onSave twice on a double click while saving", async () => {
    getTopicSuggestions.mockResolvedValue({
      suggestion_status: "ready",
      suggested_topic_ids: [1],
      suggested_new_topic_names: [],
    });
    let resolveSave: (v: unknown) => void = () => {};
    updateMyPreferences.mockReturnValue(new Promise((resolve) => (resolveSave = resolve)));
    const wrapper = mountStep();
    await flushPromises();

    const saveButton = wrapper.findAll("button").find((b) => b.text().includes("אני רוצה לקבל"))!;
    await saveButton.trigger("click");
    await saveButton.trigger("click");
    resolveSave(PREFS);
    await flushPromises();

    expect(updateMyPreferences).toHaveBeenCalledTimes(1);
  });
});
