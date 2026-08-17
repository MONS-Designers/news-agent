import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import AboutYouStep from "../AboutYouStep.vue";

const listFields = vi.fn();
const listRoles = vi.fn();
const getMyProfile = vi.fn();
const updateMyProfile = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listFields: (...args: unknown[]) => listFields(...args),
    listRoles: (...args: unknown[]) => listRoles(...args),
    getMyProfile: (...args: unknown[]) => getMyProfile(...args),
    updateMyProfile: (...args: unknown[]) => updateMyProfile(...args),
  };
});

const FIELDS = [
  { id: 1, name: "פיתוח" },
  { id: 2, name: "עיצוב" },
];
const DEV_ROLES = [
  { name: "מפתח", isCurated: true },
  { name: "מוביל צוות", isCurated: true },
];
const BLANK_PROFILE = {
  field_name: null,
  role_name: null,
  experience_bucket: null,
  interest_free_text: null,
};

beforeEach(() => {
  listFields.mockReset();
  listRoles.mockReset();
  getMyProfile.mockReset();
  updateMyProfile.mockReset();
  listFields.mockResolvedValue(FIELDS);
  listRoles.mockResolvedValue(DEV_ROLES);
  getMyProfile.mockResolvedValue(BLANK_PROFILE);
});

function fieldChip(wrapper: ReturnType<typeof mount>, name: string) {
  const groups = wrapper.findAll('[role="group"]');
  return groups[0].findAll("button").find((b) => b.text() === name)!;
}
function roleChip(wrapper: ReturnType<typeof mount>, name: string) {
  const groups = wrapper.findAll('[role="group"]');
  return groups[1].findAll("button").find((b) => b.text() === name)!;
}
function continueButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll("button").find((b) => b.text().includes("המשך"))!;
}
async function pickExperience(wrapper: ReturnType<typeof mount>, value: string) {
  const radios = wrapper.findAll('input[type="radio"]');
  const target = radios.find((r) => (r.element as HTMLInputElement).value === value)!;
  await target.setValue();
}

describe("AboutYouStep - happy path", () => {
  it("renders a brand-new user with nothing pre-filled and Continue disabled", async () => {
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    expect(continueButton(wrapper).attributes("disabled")).toBeDefined();
    expect(listRoles).not.toHaveBeenCalled();
  });

  it("fetches Field-scoped roles once a curated Field is picked, resetting any prior Role pick", async () => {
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();

    expect(listRoles).toHaveBeenCalledWith(1);
    expect(roleChip(wrapper, "מפתח")).toBeTruthy();
  });

  it("prefills a curated Field and curated Role from an existing profile", async () => {
    getMyProfile.mockResolvedValue({
      ...BLANK_PROFILE,
      field_name: "פיתוח",
      role_name: "מפתח",
      experience_bucket: "3-5",
    });
    const wrapper = mount(AboutYouStep);
    await flushPromises();
    await flushPromises(); // second tick for the Field->Role watch chain

    expect(fieldChip(wrapper, "פיתוח").attributes("aria-pressed")).toBe("true");
    expect(roleChip(wrapper, "מפתח").attributes("aria-pressed")).toBe("true");
    expect(continueButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("functionally captures an uncurated Field prefill (satisfies the gate, no curated Role fetch) even though it doesn't render as visible Other text", async () => {
    // Same root cause as the documented Role-prefill quirk below: the prefill
    // path sets ChipRow's selectedName to the actual field name (not null)
    // while isOther is also true, so ChipRow's otherButtonActive (which
    // requires selectedName === null) never becomes true here and the
    // free-text input stays hidden. The value still flows correctly into
    // canContinue and into the eventual save.
    getMyProfile.mockResolvedValue({ ...BLANK_PROFILE, field_name: "ביולוגיה ימית" });
    const wrapper = mount(AboutYouStep);
    await flushPromises();
    await flushPromises();

    expect(wrapper.find('input[type="text"]').exists()).toBe(false);
    expect(listRoles).not.toHaveBeenCalled(); // "Other" field has no curated roles by definition

    // Field alone satisfies fieldSatisfied, but Role/Experience are still
    // required for canContinue - fill those in through the (unaffected)
    // normal Other-role flow to reach a savable state.
    const roleOtherButton = wrapper
      .findAll('[role="group"]')[1]
      .findAll("button")
      .find((b) => b.text() === "אחר")!;
    await roleOtherButton.trigger("click");
    await wrapper.find('input[type="text"]').setValue("יזם עצמאי");
    await pickExperience(wrapper, "0-2");

    updateMyProfile.mockResolvedValue({});
    await continueButton(wrapper).trigger("click");
    await flushPromises();
    expect(updateMyProfile).toHaveBeenCalledWith(
      expect.objectContaining({ fieldName: "ביולוגיה ימית", fieldIsOther: true }),
    );
  });

  it("Continue emits without an API call when nothing changed since load", async () => {
    getMyProfile.mockResolvedValue({
      ...BLANK_PROFILE,
      field_name: "פיתוח",
      role_name: "מפתח",
      experience_bucket: "3-5",
    });
    const wrapper = mount(AboutYouStep);
    await flushPromises();
    await flushPromises();

    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(updateMyProfile).not.toHaveBeenCalled();
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });

  it("saves and emits continue when a selection actually changed", async () => {
    updateMyProfile.mockResolvedValue({});
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();
    await roleChip(wrapper, "מפתח").trigger("click");
    await pickExperience(wrapper, "0-2");
    await flushPromises();

    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(updateMyProfile).toHaveBeenCalledWith({
      fieldName: "פיתוח",
      fieldIsOther: false,
      roleName: "מפתח",
      roleIsOther: false,
      experienceBucket: "0-2",
    });
    expect(wrapper.emitted("continue")).toHaveLength(1);
  });
});

describe("AboutYouStep - unhappy path / edge cases", () => {
  it("shows a load error when the initial fields/profile fetch fails", async () => {
    getMyProfile.mockRejectedValue(new Error("network down"));
    const wrapper = mount(AboutYouStep);
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת האפשרויות נכשלה");
  });

  it("shows a load error when fetching Field-scoped roles fails", async () => {
    listRoles.mockRejectedValue(new Error("network down"));
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("טעינת האפשרויות נכשלה");
  });

  it("discards a stale in-flight Role fetch when the Field is changed again before it resolves", async () => {
    let resolveDevRoles: (v: unknown) => void = () => {};
    listRoles.mockImplementation((fieldId: number) => {
      if (fieldId === 1) return new Promise((resolve) => (resolveDevRoles = resolve));
      return Promise.resolve([{ name: "מעצב", isCurated: true }]);
    });
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click"); // fieldId 1, fetch left pending
    await flushPromises();
    await fieldChip(wrapper, "עיצוב").trigger("click"); // fieldId 2, resolves immediately
    await flushPromises();

    expect(roleChip(wrapper, "מעצב")).toBeTruthy();

    resolveDevRoles(DEV_ROLES); // late response for the abandoned Field 1 fetch
    await flushPromises();

    const groups = wrapper.findAll('[role="group"]');
    const roleNames = groups[1].findAll("button").map((b) => b.text());
    expect(roleNames).not.toContain("מפתח");
    expect(roleNames).toContain("מעצב");
  });

  it("clears the Role placeholder loading state even if the abandoned fetch never resolves", async () => {
    listRoles.mockImplementation((fieldId: number) => {
      if (fieldId === 1) return new Promise(() => {}); // never resolves
      return Promise.resolve([{ name: "מעצב", isCurated: true }]);
    });
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();
    await fieldChip(wrapper, "עיצוב").trigger("click");
    await flushPromises();

    expect(wrapper.text()).not.toContain("טוען תפקידים");
  });

  it("shows a save error and does not emit continue when updateMyProfile fails", async () => {
    updateMyProfile.mockRejectedValue(new Error("boom"));
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();
    await roleChip(wrapper, "מפתח").trigger("click");
    await pickExperience(wrapper, "0-2");
    await flushPromises();

    await continueButton(wrapper).trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("השמירה נכשלה");
    expect(wrapper.emitted("continue")).toBeFalsy();
  });

  it("keeps Continue disabled until Field, Role, and Experience are all satisfied", async () => {
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    await fieldChip(wrapper, "פיתוח").trigger("click");
    await flushPromises();
    expect(continueButton(wrapper).attributes("disabled")).toBeDefined();

    await roleChip(wrapper, "מפתח").trigger("click");
    expect(continueButton(wrapper).attributes("disabled")).toBeDefined(); // experience still missing

    await pickExperience(wrapper, "0-2");
    expect(continueButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("does not treat blank Other text as satisfying the Field requirement", async () => {
    const wrapper = mount(AboutYouStep);
    await flushPromises();

    const otherButton = wrapper.findAll('[role="group"]')[0].findAll("button").find((b) => b.text() === "אחר")!;
    await otherButton.trigger("click");
    await pickExperience(wrapper, "0-2");

    expect(continueButton(wrapper).attributes("disabled")).toBeDefined();
  });

  it("documents current behavior: an uncurated Role prefill that doesn't match any fetched role is saved correctly but is not visibly reflected as a selected chip or visible Other text (ChipRow's otherButtonActive requires selectedName===null, which this prefill path violates)", async () => {
    getMyProfile.mockResolvedValue({ ...BLANK_PROFILE, field_name: "פיתוח", role_name: "יזם" });
    const wrapper = mount(AboutYouStep);
    await flushPromises();
    await flushPromises();

    const roleGroup = wrapper.findAll('[role="group"]')[1];
    const pressedRoleChips = roleGroup.findAll("button").filter((b) => b.attributes("aria-pressed") === "true");
    expect(pressedRoleChips).toHaveLength(0); // nothing visibly selected...
    expect(wrapper.findAll('input[type="text"]')).toHaveLength(0); // ...and no visible text input either

    // ...yet the value is functionally captured and would be saved if Continue were clicked.
    updateMyProfile.mockResolvedValue({});
    await pickExperience(wrapper, "0-2");
    await continueButton(wrapper).trigger("click");
    await flushPromises();
    expect(updateMyProfile).toHaveBeenCalledWith(
      expect.objectContaining({ roleName: "יזם", roleIsOther: true }),
    );
  });
});
