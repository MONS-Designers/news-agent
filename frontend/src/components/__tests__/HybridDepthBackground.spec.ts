import { describe, it, expect, afterEach } from "vitest";
import { mount } from "@vue/test-utils";
import HybridDepthBackground from "../HybridDepthBackground.vue";

const originalMatchMedia = window.matchMedia;

afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

/** Query-aware matchMedia stub - test-setup.ts's default mock always reports
 * `matches: false` regardless of the query, which can't exercise the
 * reduced-motion branch. Only the reduced-motion query is made to match;
 * every other query (e.g. the hover query) behaves like the default mock. */
function stubReducedMotion(matches: boolean) {
  window.matchMedia = ((media: string) =>
    ({
      matches: media.includes("prefers-reduced-motion") ? matches : false,
      media,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    }) as unknown as MediaQueryList) as typeof window.matchMedia;
}

/** Same idea, but also makes the hover-capable-pointer query match true -
 * needed to exercise the mousemove path, since the component only attaches
 * its mousemove listener when `(hover: hover) and (pointer: fine)` matches. */
function stubReducedMotionAndHover(reducedMotionMatches: boolean) {
  window.matchMedia = ((media: string) =>
    ({
      matches: media.includes("prefers-reduced-motion") ? reducedMotionMatches : media.includes("hover"),
      media,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => true,
    }) as unknown as MediaQueryList) as typeof window.matchMedia;
}

describe("HybridDepthBackground", () => {
  it("renders its default slot content inside the void/orb chrome", () => {
    const wrapper = mount(HybridDepthBackground, {
      slots: { default: '<p class="slot-content">Hello</p>' },
    });
    expect(wrapper.find(".slot-content").exists()).toBe(true);
    expect(wrapper.text()).toContain("Hello");
  });

  it("mounts and unmounts cleanly (matchMedia/scroll listeners attach and detach without throwing)", () => {
    const wrapper = mount(HybridDepthBackground);
    expect(() => wrapper.unmount()).not.toThrow();
  });

  it("freezes orb transforms under prefers-reduced-motion", () => {
    stubReducedMotion(true);
    const wrapper = mount(HybridDepthBackground);

    const orbs = wrapper.find('[aria-hidden="true"]').findAll("div");
    expect(orbs).toHaveLength(3);
    orbs.forEach((orb) => {
      expect(orb.attributes("style")).toContain("translate(0, 0)");
    });
  });

  it("actually moves the orbs on mousemove when prefers-reduced-motion is off (not just 'doesn't freeze')", () => {
    stubReducedMotionAndHover(false);
    const wrapper = mount(HybridDepthBackground);
    const orbs = wrapper.find('[aria-hidden="true"]').findAll("div");

    // Before any mousemove, applyOrbTransforms has never run - no inline
    // style at all yet (distinct from the frozen "translate(0, 0)" case).
    orbs.forEach((orb) => expect(orb.attributes("style")).toBeUndefined());

    window.dispatchEvent(
      new MouseEvent("mousemove", { clientX: window.innerWidth, clientY: window.innerHeight }),
    );

    orbs.forEach((orb) => {
      const style = orb.attributes("style") ?? "";
      expect(style).toContain("translate(");
      expect(style).not.toBe("transform: translate(0, 0);");
    });
  });
});
