import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import FeedbackWidget from "../FeedbackWidget.vue";
import { submitFeedback } from "@/api/client";

vi.mock("@/api/client", () => ({
  submitFeedback: vi.fn(async () => {}),
}));

const Blank = { template: "<div>page</div>" };

async function mountWidget() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/", component: Blank }],
  });
  await router.push("/");
  const wrapper = mount(FeedbackWidget, { global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

function faces(wrapper: Awaited<ReturnType<typeof mountWidget>>) {
  return wrapper.findAll('[role="radiogroup"] button');
}

beforeEach(() => {
  vi.mocked(submitFeedback).mockClear();
});

describe("FeedbackWidget - happy path", () => {
  it("opens the panel with five unselected rating faces, not stars or thumbs", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");

    const buttons = faces(wrapper);
    expect(buttons).toHaveLength(5);
    expect(buttons.every((b) => b.attributes("aria-pressed") === "false")).toBe(true);
    expect(wrapper.text()).not.toContain("★");
    expect(wrapper.text()).not.toContain("👍");
    expect(wrapper.text()).not.toContain("👎");
  });

  it("clicking the 4th face marks only that one pressed (discrete, not cumulative like stars)", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");
    await faces(wrapper)[3].trigger("click");

    const buttons = faces(wrapper);
    expect(buttons.map((b) => b.attributes("aria-pressed"))).toEqual([
      "false",
      "false",
      "false",
      "true",
      "false",
    ]);
  });

  it("clicking the same face again deselects it (toggle off)", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");
    await faces(wrapper)[2].trigger("click");
    await faces(wrapper)[2].trigger("click");

    expect(faces(wrapper).every((b) => b.attributes("aria-pressed") === "false")).toBe(true);
  });

  it("picking a different face moves the selection instead of adding to it", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");
    await faces(wrapper)[1].trigger("click");
    await faces(wrapper)[4].trigger("click");

    const buttons = faces(wrapper);
    expect(buttons[1].attributes("aria-pressed")).toBe("false");
    expect(buttons[4].attributes("aria-pressed")).toBe("true");
  });

  it("submits the numeric rating (not up/down) and the trimmed note", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");
    await faces(wrapper)[4].trigger("click");
    await wrapper.find("textarea").setValue("  מעולה  ");

    const submitButton = wrapper.findAll("button").find((b) => b.text() === "שליחה")!;
    await submitButton.trigger("click");
    await flushPromises();

    expect(submitFeedback).toHaveBeenCalledWith(5, "מעולה");
    expect(wrapper.text()).toContain("תודה");
  });
});

describe("FeedbackWidget - unhappy path / edge cases", () => {
  it("disables submit with no rating and no text", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");

    const submitButton = wrapper.findAll("button").find((b) => b.text() === "שליחה")!;
    expect(submitButton.attributes("disabled")).toBeDefined();
  });

  it("enables submit once a face is picked, with no text at all", async () => {
    const wrapper = await mountWidget();
    await wrapper.find("button").trigger("click");
    await faces(wrapper)[0].trigger("click");

    const submitButton = wrapper.findAll("button").find((b) => b.text() === "שליחה")!;
    expect(submitButton.attributes("disabled")).toBeUndefined();
  });
});
