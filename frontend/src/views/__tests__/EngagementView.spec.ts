import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";
import EngagementView from "../EngagementView.vue";
import { ApiError } from "@/api/client";

const listDigestEngagement = vi.fn();
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listDigestEngagement: (...args: unknown[]) => listDigestEngagement(...args),
  };
});

const ROWS = [
  {
    digest_id: 1,
    user_email: "a@example.com",
    date: "2026-08-10",
    sent_at: "2026-08-10T08:00:00Z",
    opened_at: "2026-08-10T09:00:00Z",
    articles_total: 5,
    articles_clicked: 2,
    clicked_article_titles: ["כתבה א", "כתבה ב"],
    preferences_clicked: true,
  },
  {
    digest_id: 2,
    user_email: "b@example.com",
    date: "2026-08-10",
    sent_at: "2026-08-10T08:00:00Z",
    opened_at: null,
    articles_total: 3,
    articles_clicked: 0,
    clicked_article_titles: [],
    preferences_clicked: false,
  },
];

beforeEach(() => {
  listDigestEngagement.mockReset();
});

describe("EngagementView - happy path", () => {
  it("loads and renders engagement rows on mount", async () => {
    listDigestEngagement.mockResolvedValue(ROWS);
    const wrapper = mount(EngagementView);
    await flushPromises();

    const rows = wrapper.findAll("li");
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain("a@example.com");
    expect(rows[0].text()).toContain("נפתח");
    expect(rows[0].text()).toContain("2 מתוך 5");
    expect(rows[0].text()).toContain("העדפות נלחצו");
    expect(rows[0].text()).toContain("כתבה א, כתבה ב");
  });

  it("shows a not-opened / not-clicked badge and no click list for a digest with no engagement", async () => {
    listDigestEngagement.mockResolvedValue(ROWS);
    const wrapper = mount(EngagementView);
    await flushPromises();

    const secondRow = wrapper.findAll("li")[1];
    expect(secondRow.text()).toContain("לא נפתח");
    expect(secondRow.text()).toContain("העדפות לא נלחצו");
    expect(secondRow.text()).not.toContain("נלחצו:");
  });

  it("shows the empty state when no digests have been sent", async () => {
    listDigestEngagement.mockResolvedValue([]);
    const wrapper = mount(EngagementView);
    await flushPromises();
    expect(wrapper.text()).toContain("עדיין לא נשלחו מיילים");
  });

  it("reloads on the refresh button", async () => {
    listDigestEngagement.mockResolvedValue([]);
    const wrapper = mount(EngagementView);
    await flushPromises();
    expect(listDigestEngagement).toHaveBeenCalledTimes(1);

    listDigestEngagement.mockResolvedValue(ROWS);
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(listDigestEngagement).toHaveBeenCalledTimes(2);
    expect(wrapper.findAll("li")).toHaveLength(2);
  });
});

describe("EngagementView - unhappy path / edge cases", () => {
  it("shows a sign-in message on a 401", async () => {
    listDigestEngagement.mockRejectedValue(new ApiError(401, "unauthorized"));
    const wrapper = mount(EngagementView);
    await flushPromises();
    expect(wrapper.text()).toContain("התחבר עם Google");
  });

  it("shows a permissions message on a 403", async () => {
    listDigestEngagement.mockRejectedValue(new ApiError(403, "forbidden"));
    const wrapper = mount(EngagementView);
    await flushPromises();
    expect(wrapper.text()).toContain("אין הרשאת מנהל");
  });

  it("shows a generic error message on any other failure", async () => {
    listDigestEngagement.mockRejectedValue(new Error("network down"));
    const wrapper = mount(EngagementView);
    await flushPromises();
    expect(wrapper.text()).toContain("טעינת נתוני המעורבות נכשלה");
  });

  it("shows the loading state before the request resolves", async () => {
    let resolveLoad: (v: unknown) => void = () => {};
    listDigestEngagement.mockReturnValue(new Promise((resolve) => (resolveLoad = resolve)));
    const wrapper = mount(EngagementView);
    await nextTick();
    expect(wrapper.text()).toContain("טוען");

    resolveLoad([]);
    await flushPromises();
    expect(wrapper.text()).not.toContain("טוען");
  });
});
