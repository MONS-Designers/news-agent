import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import TaxonomyQueueView from "../TaxonomyQueueView.vue";
import { ApiError } from "@/api/client";

const listPendingTaxonomySuggestions = vi.fn();
const decideTaxonomySuggestion = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listPendingTaxonomySuggestions: (...args: unknown[]) => listPendingTaxonomySuggestions(...args),
    decideTaxonomySuggestion: (...args: unknown[]) => decideTaxonomySuggestion(...args),
  };
});

const FIELD_SUGGESTION = { id: 1, kind: "field", field_name: null, text: "ביולוגיה ימית", submission_count: 2 };
const ROLE_SUGGESTION = { id: 2, kind: "role", field_name: "פיתוח", text: "מהנדס נתונים", submission_count: 1 };
const ORPHAN_ROLE = { id: 3, kind: "role", field_name: null, text: "יחסי מפתחים", submission_count: 1 };

beforeEach(() => {
  listPendingTaxonomySuggestions.mockReset();
  decideTaxonomySuggestion.mockReset();
});

describe("TaxonomyQueueView - happy path", () => {
  it("groups field suggestions and role suggestions by their curated field", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([FIELD_SUGGESTION, ROLE_SUGGESTION]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const sections = wrapper.findAll("section");
    expect(sections).toHaveLength(2);
    expect(sections[0].text()).toContain("תחומים חדשים");
    expect(sections[0].text()).toContain("ביולוגיה ימית");
    expect(sections[1].text()).toContain('תפקידים תחת "פיתוח"');
    expect(sections[1].text()).toContain("מהנדס נתונים");
  });

  it("pre-fills the curated-name input with the submitted text", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([FIELD_SUGGESTION]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const input = wrapper.find("input");
    expect((input.element as HTMLInputElement).value).toBe("ביולוגיה ימית");
  });

  it("shows a single-submission label without a count for a suggestion submitted once", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([ORPHAN_ROLE]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("הגשה אחת");
  });

  it("shows a submission count for a suggestion submitted more than once", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([FIELD_SUGGESTION]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("2 הגשות");
  });

  it("shows the empty state when there are no pending suggestions", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("אין הצעות טקסונומיה ממתינות");
  });
});

describe("TaxonomyQueueView - unhappy path / edge cases", () => {
  it("groups an orphan role (uncurated parent field) into its own blocked bucket, distinct from promotable role groups", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([ROLE_SUGGESTION, ORPHAN_ROLE]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const sections = wrapper.findAll("section");
    expect(sections).toHaveLength(2);
    const blockedSection = sections.find((s) => s.text().includes("ממתין לתחום"))!;
    expect(blockedSection.text()).toContain("יחסי מפתחים");
    expect(blockedSection.text()).toContain("התחום שהתפקידים האלה הוגשו תחתיו טרם אושר");
  });

  it("disables Promote (but not Reject) for an orphan role", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([ORPHAN_ROLE]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const buttons = wrapper.find("li").findAll("button");
    const [promote, reject] = buttons;
    expect(promote.text()).toBe("קידום");
    expect(promote.attributes("disabled")).toBeDefined();
    expect(reject.attributes("disabled")).toBeUndefined();
  });

  it("disables the curated-name input for an orphan role", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([ORPHAN_ROLE]);
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.find("input").attributes("disabled")).toBeDefined();
  });

  it("rejects an orphan role successfully even though promote is disabled", async () => {
    listPendingTaxonomySuggestions.mockResolvedValueOnce([ORPHAN_ROLE]).mockResolvedValueOnce([]);
    decideTaxonomySuggestion.mockResolvedValue({ ...ORPHAN_ROLE, status: "rejected" });
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const rejectButton = wrapper.find("li").findAll("button")[1];
    await rejectButton.trigger("click");
    await flushPromises();

    expect(decideTaxonomySuggestion).toHaveBeenCalledWith(3, "rejected", undefined);
    expect(listPendingTaxonomySuggestions).toHaveBeenCalledTimes(2);
  });

  it("sends the edited curated name (not the original text) when promoting", async () => {
    listPendingTaxonomySuggestions.mockResolvedValueOnce([FIELD_SUGGESTION]).mockResolvedValueOnce([]);
    decideTaxonomySuggestion.mockResolvedValue({ ...FIELD_SUGGESTION });
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    await wrapper.find("input").setValue("Marine Biology");
    const promoteButton = wrapper.find("li").findAll("button")[0];
    await promoteButton.trigger("click");
    await flushPromises();

    expect(decideTaxonomySuggestion).toHaveBeenCalledWith(1, "approved", "Marine Biology");
  });

  it("does not send a curated name when rejecting", async () => {
    listPendingTaxonomySuggestions.mockResolvedValueOnce([FIELD_SUGGESTION]).mockResolvedValueOnce([]);
    decideTaxonomySuggestion.mockResolvedValue({ ...FIELD_SUGGESTION });
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const rejectButton = wrapper.find("li").findAll("button")[1];
    await rejectButton.trigger("click");
    await flushPromises();

    expect(decideTaxonomySuggestion).toHaveBeenCalledWith(1, "rejected", undefined);
  });

  it("reloads the full queue after a decision instead of just filtering the local row (field approval can unblock roles)", async () => {
    listPendingTaxonomySuggestions
      .mockResolvedValueOnce([FIELD_SUGGESTION, ORPHAN_ROLE])
      .mockResolvedValueOnce([{ ...ROLE_SUGGESTION, field_name: "ביולוגיה ימית" }]);
    decideTaxonomySuggestion.mockResolvedValue({ ...FIELD_SUGGESTION, status: "approved" });
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const promoteButton = wrapper.findAll("li")[0].findAll("button")[0];
    await promoteButton.trigger("click");
    await flushPromises();

    expect(listPendingTaxonomySuggestions).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain('תפקידים תחת "ביולוגיה ימית"');
  });

  it("shows an action error and keeps the row when a decision fails", async () => {
    listPendingTaxonomySuggestions.mockResolvedValue([FIELD_SUGGESTION]);
    decideTaxonomySuggestion.mockRejectedValue(new Error("boom"));
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();

    const promoteButton = wrapper.find("li").findAll("button")[0];
    await promoteButton.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("הפעולה נכשלה");
    expect(wrapper.text()).toContain("לקדם");
    expect(wrapper.findAll("li")).toHaveLength(1);
  });

  it("shows a sign-in message on a 401", async () => {
    listPendingTaxonomySuggestions.mockRejectedValue(new ApiError(401, "unauthorized"));
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("התחבר עם Google");
  });

  it("shows a permissions message on a 403", async () => {
    listPendingTaxonomySuggestions.mockRejectedValue(new ApiError(403, "forbidden"));
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("אין הרשאת מנהל");
  });

  it("shows a generic error message on any other load failure", async () => {
    listPendingTaxonomySuggestions.mockRejectedValue(new Error("network down"));
    const wrapper = mount(TaxonomyQueueView);
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת הצעות הטקסונומיה נכשלה");
  });
});
