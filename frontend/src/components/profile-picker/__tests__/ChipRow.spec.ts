import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import ChipRow from "../ChipRow.vue";

const OPTIONS = [
  { id: 1, name: "פיתוח", isCurated: true },
  { id: null, name: "רעיון-חדש", isCurated: false },
];

function mountRow(overrides: Record<string, unknown> = {}) {
  return mount(ChipRow, {
    props: {
      stepNum: "1",
      label: "תחום",
      options: OPTIONS,
      otherPlaceholder: "התחום שלך",
      placeholderText: null,
      selectedName: null,
      isOther: false,
      otherText: "",
      ...overrides,
    },
  });
}

function chipByText(wrapper: ReturnType<typeof mountRow>, text: string) {
  return wrapper.findAll('[role="group"] button').find((b) => b.text() === text)!;
}

describe("ChipRow - happy path", () => {
  it("selecting a curated chip marks it selected and clears stale other-state", async () => {
    // Starts from a dirty Other state (as if the user had typed something
    // under Other before picking a curated chip instead) so the clearing
    // is actually observable, not a same-value no-op.
    const wrapper = mountRow({ selectedName: null, isOther: true, otherText: "leftover" });
    await chipByText(wrapper, "פיתוח").trigger("click");

    expect(wrapper.emitted("update:selectedName")![0]).toEqual(["פיתוח"]);
    expect(wrapper.emitted("update:isOther")![0]).toEqual([false]);
    expect(wrapper.emitted("update:otherText")![0]).toEqual([""]);
    expect(chipByText(wrapper, "פיתוח").attributes("aria-pressed")).toBe("true");
  });

  it("selecting a not-yet-curated ('new') chip renders it as selected but marks isOther", async () => {
    const wrapper = mountRow();
    await chipByText(wrapper, "רעיון-חדש").trigger("click");

    expect(wrapper.emitted("update:selectedName")![0]).toEqual(["רעיון-חדש"]);
    expect(wrapper.emitted("update:isOther")![0]).toEqual([true]);
    expect(wrapper.emitted("update:otherText")![0]).toEqual(["רעיון-חדש"]);
    expect(chipByText(wrapper, "רעיון-חדש").attributes("aria-pressed")).toBe("true");

    // otherButtonActive must stay false for a "new" chip pick - it is not the
    // genuine Other button, so the free-text input must not appear either.
    const otherButton = wrapper.findAll('[role="group"] button').find((b) => b.text() === "אחר")!;
    expect(otherButton.attributes("aria-pressed")).toBe("false");
    expect(wrapper.find("input").exists()).toBe(false);
  });

  it("selecting Other clears any prior selection and reveals the free-text input", async () => {
    const wrapper = mountRow({ selectedName: "פיתוח", isOther: false, otherText: "stale" });
    const otherButton = wrapper.findAll('[role="group"] button').find((b) => b.text() === "אחר")!;
    await otherButton.trigger("click");

    expect(wrapper.emitted("update:selectedName")![0]).toEqual([null]);
    expect(wrapper.emitted("update:isOther")![0]).toEqual([true]);
    expect(wrapper.emitted("update:otherText")![0]).toEqual([""]);
    expect(otherButton.attributes("aria-pressed")).toBe("true");
    expect(wrapper.find("input").exists()).toBe(true);
  });

  it("free-text input reflects typed value up to the server-mirrored max length", async () => {
    const wrapper = mountRow({ selectedName: null, isOther: true, otherText: "" });
    const input = wrapper.find("input");
    expect(input.attributes("maxlength")).toBe("100");
    await input.setValue("תחום מותאם אישית");
    const otherTextEvents = wrapper.emitted("update:otherText")!;
    expect(otherTextEvents[otherTextEvents.length - 1]).toEqual(["תחום מותאם אישית"]);
  });
});

describe("ChipRow - unhappy path / edge cases", () => {
  it("clears stale free-text when switching back to Other after it was already active", async () => {
    // Simulates: user typed something under Other, then picked a curated chip
    // elsewhere, then returns to Other - stale text must not resubmit.
    const wrapper = mountRow({ selectedName: null, isOther: true, otherText: "leftover text" });
    const otherButton = wrapper.findAll('[role="group"] button').find((b) => b.text() === "אחר")!;
    await otherButton.trigger("click");

    const otherTextEvents = wrapper.emitted("update:otherText")!;
    expect(otherTextEvents[otherTextEvents.length - 1]).toEqual([""]);
  });

  it("renders only placeholder text when placeholderText is set, hiding chips and the input", () => {
    const wrapper = mountRow({ placeholderText: "בחר תחום קודם", isOther: true });
    expect(wrapper.text()).toContain("בחר תחום קודם");
    expect(wrapper.find('[role="group"]').exists()).toBe(false);
    expect(wrapper.find("input").exists()).toBe(false);
  });

  it("does not mark the Other button active when isOther is true but a chip name is still set (stale parent reset guard)", () => {
    // otherButtonActive is a derived computed specifically to avoid this
    // becoming stale if a parent resets isOther without clearing selectedName.
    const wrapper = mountRow({ selectedName: "פיתוח", isOther: true, otherText: "" });
    const otherButton = wrapper.findAll('[role="group"] button').find((b) => b.text() === "אחר")!;
    expect(otherButton.attributes("aria-pressed")).toBe("false");
    expect(wrapper.find("input").exists()).toBe(false);
  });

  it("treats an unset isCurated as curated by default", async () => {
    const wrapper = mountRow({
      options: [{ id: 9, name: "ברירת מחדל" }],
      isOther: true,
      otherText: "leftover",
    });
    await chipByText(wrapper, "ברירת מחדל").trigger("click");
    // Curated path clears otherText/isOther, unlike selectNew.
    expect(wrapper.emitted("update:isOther")![0]).toEqual([false]);
    expect(wrapper.emitted("update:otherText")![0]).toEqual([""]);
  });

  it("deselects a curated chip's isChipSelected once isOther becomes true for the same name", () => {
    // A curated option is only "selected" when its name matches AND isOther
    // is false - if isOther flips true for the same name, the curated chip
    // itself must show unselected (this exact state is unreachable through
    // the row's own handlers, but the derivation must hold defensively).
    const wrapper = mountRow({ selectedName: "פיתוח", isOther: true, otherText: "פיתוח" });
    expect(chipByText(wrapper, "פיתוח").attributes("aria-pressed")).toBe("false");
  });
});
