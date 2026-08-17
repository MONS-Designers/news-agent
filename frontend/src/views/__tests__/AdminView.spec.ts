import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import AdminView from "../AdminView.vue";
import { ApiError } from "@/api/client";

const listPendingSources = vi.fn();
const setSourceStatus = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listPendingSources: (...args: unknown[]) => listPendingSources(...args),
    setSourceStatus: (...args: unknown[]) => setSourceStatus(...args),
  };
});

const SOURCES = [
  { id: 1, topic_id: 1, url: "https://a.example", name: "Source A", status: "pending" },
  { id: 2, topic_id: 2, url: "https://b.example", name: "Source B", status: "pending" },
];

beforeEach(() => {
  listPendingSources.mockReset();
  setSourceStatus.mockReset();
});

describe("AdminView - happy path", () => {
  it("loads and renders pending sources on mount", async () => {
    listPendingSources.mockResolvedValue(SOURCES);
    const wrapper = mount(AdminView);
    await flushPromises();

    expect(wrapper.findAll("li")).toHaveLength(2);
    expect(wrapper.text()).toContain("Source A");
    expect(wrapper.text()).toContain("ממתין");
  });

  it("approves a source and removes it from the list", async () => {
    listPendingSources.mockResolvedValue(SOURCES);
    setSourceStatus.mockResolvedValue({ ...SOURCES[0], status: "approved" });
    const wrapper = mount(AdminView);
    await flushPromises();

    const approveButton = wrapper.findAll("li")[0].findAll("button")[0];
    await approveButton.trigger("click");
    await flushPromises();

    expect(setSourceStatus).toHaveBeenCalledWith(1, "approved");
    expect(wrapper.findAll("li")).toHaveLength(1);
    expect(wrapper.text()).not.toContain("Source A");
  });

  it("rejects a source and removes it from the list", async () => {
    listPendingSources.mockResolvedValue(SOURCES);
    setSourceStatus.mockResolvedValue({ ...SOURCES[1], status: "rejected" });
    const wrapper = mount(AdminView);
    await flushPromises();

    const rejectButton = wrapper.findAll("li")[1].findAll("button")[1];
    await rejectButton.trigger("click");
    await flushPromises();

    expect(setSourceStatus).toHaveBeenCalledWith(2, "rejected");
    expect(wrapper.findAll("li")).toHaveLength(1);
  });

  it("shows the empty state when there are no pending sources", async () => {
    listPendingSources.mockResolvedValue([]);
    const wrapper = mount(AdminView);
    await flushPromises();

    expect(wrapper.text()).toContain("אין מקורות ממתינים");
  });

  it("reloads sources when the refresh button is clicked", async () => {
    listPendingSources.mockResolvedValue([]);
    const wrapper = mount(AdminView);
    await flushPromises();
    expect(listPendingSources).toHaveBeenCalledTimes(1);

    listPendingSources.mockResolvedValue(SOURCES);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(listPendingSources).toHaveBeenCalledTimes(2);
    expect(wrapper.findAll("li")).toHaveLength(2);
  });
});

describe("AdminView - unhappy path / edge cases", () => {
  it("shows a sign-in message on a 401", async () => {
    listPendingSources.mockRejectedValue(new ApiError(401, "unauthorized"));
    const wrapper = mount(AdminView);
    await flushPromises();
    expect(wrapper.text()).toContain("התחבר עם Google");
  });

  it("shows a permissions message on a 403", async () => {
    listPendingSources.mockRejectedValue(new ApiError(403, "forbidden"));
    const wrapper = mount(AdminView);
    await flushPromises();
    expect(wrapper.text()).toContain("אין הרשאת מנהל");
  });

  it("shows a generic error message on any other failure", async () => {
    listPendingSources.mockRejectedValue(new Error("network down"));
    const wrapper = mount(AdminView);
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת המקורות נכשלה");
  });

  it("shows an action error and keeps the row when approving fails, without touching other rows", async () => {
    listPendingSources.mockResolvedValue(SOURCES);
    setSourceStatus.mockRejectedValue(new Error("boom"));
    const wrapper = mount(AdminView);
    await flushPromises();

    const approveButton = wrapper.findAll("li")[0].findAll("button")[0];
    await approveButton.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("הפעולה נכשלה");
    expect(wrapper.text()).toContain("לאשר");
    expect(wrapper.findAll("li")).toHaveLength(2);
  });

  it("disables both action buttons on a row only while its own action is pending", async () => {
    listPendingSources.mockResolvedValue(SOURCES);
    let resolveAction: (v: unknown) => void = () => {};
    setSourceStatus.mockReturnValue(new Promise((resolve) => (resolveAction = resolve)));
    const wrapper = mount(AdminView);
    await flushPromises();

    const rows = wrapper.findAll("li");
    const firstRowButtons = rows[0].findAll("button");
    await firstRowButtons[0].trigger("click");
    await flushPromises();

    expect(firstRowButtons[0].attributes("disabled")).toBeDefined();
    expect(firstRowButtons[1].attributes("disabled")).toBeDefined();
    const secondRowButtons = rows[1].findAll("button");
    expect(secondRowButtons[0].attributes("disabled")).toBeUndefined();

    resolveAction({ ...SOURCES[0], status: "approved" });
    await flushPromises();
  });
});
