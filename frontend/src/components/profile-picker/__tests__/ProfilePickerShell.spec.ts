import { describe, it, expect } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import HybridDepthBackground from "@/components/HybridDepthBackground.vue";
import ProfilePickerShell from "../ProfilePickerShell.vue";

const AboutYouStepStub = {
  props: ["showBack"],
  emits: ["continue", "back"],
  template: `<div>
    <button class="stub-about-continue" @click="$emit('continue')">about-continue</button>
    <button class="stub-about-back" :data-show-back="showBack" @click="$emit('back')">about-back</button>
  </div>`,
};
const InterestsStepStub = {
  props: ["active"],
  emits: ["continue", "back"],
  template: `<div class="stub-interests" :data-active="active">
    <button class="stub-interests-continue" @click="$emit('continue')">interests-continue</button>
    <button class="stub-interests-back" @click="$emit('back')">interests-back</button>
  </div>`,
};
const TopicsStepStub = {
  props: ["active"],
  emits: ["back", "saved"],
  template: `<div class="stub-topics" :data-active="active">
    <button class="stub-topics-back" @click="$emit('back')">topics-back</button>
    <button class="stub-topics-saved" @click="$emit('saved')">topics-saved</button>
  </div>`,
};

function mountShell(props: { canExit?: boolean } = {}) {
  return mount(ProfilePickerShell, {
    props,
    global: {
      stubs: {
        AboutYouStep: AboutYouStepStub,
        InterestsStep: InterestsStepStub,
        TopicsStep: TopicsStepStub,
      },
    },
  });
}

describe("ProfilePickerShell - happy path", () => {
  it("starts on Step 1 with only the About-You panel visible", () => {
    const wrapper = mountShell();
    expect(wrapper.find(".stub-about-continue").isVisible()).toBe(true);
    expect(wrapper.find(".stub-interests").isVisible()).toBe(false);
    expect(wrapper.find(".stub-topics").isVisible()).toBe(false);
  });

  it("advances Step 1 -> Step 2 and marks InterestsStep active", async () => {
    const wrapper = mountShell();
    await wrapper.find(".stub-about-continue").trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-interests").isVisible()).toBe(true);
    expect(wrapper.find(".stub-interests").attributes("data-active")).toBe("true");
    expect(wrapper.find(".stub-about-continue").isVisible()).toBe(false);
  });

  it("advances Step 2 -> Step 3 and marks TopicsStep active (InterestsStep no longer active)", async () => {
    const wrapper = mountShell();
    await wrapper.find(".stub-about-continue").trigger("click");
    await wrapper.find(".stub-interests-continue").trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-topics").isVisible()).toBe(true);
    expect(wrapper.find(".stub-topics").attributes("data-active")).toBe("true");
    expect(wrapper.find(".stub-interests").attributes("data-active")).toBe("false");
  });

  it("re-emits TopicsStep's 'saved' event as its own 'topics-saved'", async () => {
    const wrapper = mountShell();
    await wrapper.find(".stub-about-continue").trigger("click");
    await wrapper.find(".stub-interests-continue").trigger("click");
    await wrapper.find(".stub-topics-saved").trigger("click");

    expect(wrapper.emitted("topics-saved")).toHaveLength(1);
  });

  it("renders the 3-step progress indicator", () => {
    const wrapper = mountShell();
    const indicator = wrapper.find('[aria-label="התקדמות ההגדרה"]');
    expect(indicator.text()).toContain("עליך");
    expect(indicator.text()).toContain("תחומי עניין");
    expect(indicator.text()).toContain("נושאים");
  });
});

describe("ProfilePickerShell - back navigation / edge cases", () => {
  it("Step 2's back returns to Step 1 without losing Step 1's mounted state (v-show, not v-if)", async () => {
    const wrapper = mountShell();
    await wrapper.find(".stub-about-continue").trigger("click");
    await wrapper.find(".stub-interests-back").trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-about-continue").isVisible()).toBe(true);
    expect(wrapper.find(".stub-interests").isVisible()).toBe(false);
    // Step 1 was never unmounted - the same stub instance is still in the DOM.
    expect(wrapper.find(".stub-about-continue").exists()).toBe(true);
  });

  it("Step 3's back returns to Step 2 and re-activates InterestsStep", async () => {
    const wrapper = mountShell();
    await wrapper.find(".stub-about-continue").trigger("click");
    await wrapper.find(".stub-interests-continue").trigger("click");
    await wrapper.find(".stub-topics-back").trigger("click");
    await flushPromises();

    expect(wrapper.find(".stub-interests").isVisible()).toBe(true);
    expect(wrapper.find(".stub-interests").attributes("data-active")).toBe("true");
    expect(wrapper.find(".stub-topics").attributes("data-active")).toBe("false");
  });

  it("mounts and unmounts cleanly", () => {
    const wrapper = mountShell();
    expect(() => wrapper.unmount()).not.toThrow();
  });

  it("hands Step 1's Back up to its caller instead of handling it - there is no step behind Step 1", async () => {
    const wrapper = mountShell({ canExit: true });
    expect(wrapper.find(".stub-about-back").attributes("data-show-back")).toBe("true");

    await wrapper.find(".stub-about-back").trigger("click");
    expect(wrapper.emitted("back")).toHaveLength(1);
    // Still on Step 1 - the shell does not move anywhere itself.
    expect(wrapper.find(".stub-about-continue").isVisible()).toBe(true);
  });

  it("passes canExit through to Step 1, so a caller with nothing behind the wizard gets no Back there", () => {
    expect(mountShell().find(".stub-about-back").attributes("data-show-back")).toBe("false");
  });

  it("owns neither the screen's background nor its heading - PreferencesView does", () => {
    // Both used to live here, which stacked two headings (this one and the
    // page's own) the moment the wizard opened, and made a single-background
    // screen impossible.
    const wrapper = mountShell();
    expect(wrapper.findComponent(HybridDepthBackground).exists()).toBe(false);
    expect(wrapper.text()).not.toContain("הגדרת הפרופיל שלך");
    expect(wrapper.text()).toContain("עליך"); // the stepper it does still own
  });
});
