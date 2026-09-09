<template>
  <svg
    :class="[
      'inline-block text-hd-accent',
      size === 'standalone' ? 'h-[22px] w-[22px]' : 'h-[16px] w-[16px]',
    ]"
    viewBox="0 0 64 64"
    aria-hidden="true"
  >
    <g class="origin-[32px_32px] animate-hd-twinkle motion-reduce:animate-none">
      <g transform="translate(32,32) scale(2.4) translate(-46,-17)">
        <path
          d="M46,9 C46,13 42,17 38,17 C42,17 46,21 46,25 C46,21 50,17 54,17 C50,17 46,13 46,9 Z"
          fill="currentColor"
        />
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
// {components.spinner} - Hybrid Depth UX spine (DESIGN.md, 2026-09-08 revision).
// A single sparkle from the logo mark (frontend/src/assets/logo-mark.svg),
// currentColor-filled (never the mark's literal gold), twinkling in place -
// not rotating, since the sparkle is 4-fold symmetric and a spin just reads
// as a wobble at this size.
defineProps<{ size: "inline" | "standalone" }>();
</script>
