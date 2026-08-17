// jsdom implements neither matchMedia nor IntersectionObserver. Several
// components (ProfilePickerShell, HomeView, App) call these unconditionally
// in onMounted, so every test using them - not just the ones asserting on
// motion/scroll behavior - needs the environment to not crash on mount.
class MockMediaQueryList {
  matches = false;
  media: string;
  onchange = null;
  private listeners = new Set<(e: MediaQueryListEvent) => void>();

  constructor(media: string) {
    this.media = media;
  }

  addEventListener(_type: string, listener: (e: MediaQueryListEvent) => void) {
    this.listeners.add(listener);
  }
  removeEventListener(_type: string, listener: (e: MediaQueryListEvent) => void) {
    this.listeners.delete(listener);
  }
  dispatchEvent(): boolean {
    return true;
  }
  addListener() {}
  removeListener() {}
}

if (!window.matchMedia) {
  window.matchMedia = ((media: string) =>
    new MockMediaQueryList(media)) as unknown as typeof window.matchMedia;
}

if (!window.IntersectionObserver) {
  window.IntersectionObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  } as unknown as typeof IntersectionObserver;
}
