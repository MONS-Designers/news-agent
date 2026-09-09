import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import HybridSpinner from "../HybridSpinner.vue";

describe("HybridSpinner", () => {
  it("renders a single-sparkle SVG sized for the standalone context", () => {
    const wrapper = mount(HybridSpinner, { props: { size: "standalone" } });
    const svg = wrapper.find("svg");
    expect(svg.exists()).toBe(true);
    expect(svg.attributes("viewBox")).toBe("0 0 64 64");
    expect(svg.attributes("aria-hidden")).toBe("true");
    expect(svg.classes()).toEqual(expect.arrayContaining(["h-[22px]", "w-[22px]"]));
    // Exactly one sparkle path (the mark's second sparkle and 3 bars are dropped).
    expect(wrapper.findAll("path")).toHaveLength(1);
    expect(wrapper.find("path").attributes("fill")).toBe("currentColor");
  });

  it("renders smaller for the inline context", () => {
    const wrapper = mount(HybridSpinner, { props: { size: "inline" } });
    expect(wrapper.find("svg").classes()).toEqual(expect.arrayContaining(["h-[16px]", "w-[16px]"]));
  });

  it("freezes the twinkle under prefers-reduced-motion via the motion-reduce:animate-none utility", () => {
    const wrapper = mount(HybridSpinner, { props: { size: "standalone" } });
    const spark = wrapper.find("g");
    expect(spark.classes()).toContain("animate-hd-twinkle");
    expect(spark.classes()).toContain("motion-reduce:animate-none");
  });
});
