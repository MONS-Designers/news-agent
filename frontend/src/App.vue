<template>
  <div class="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
    <header class="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div class="mx-auto flex max-w-4xl items-center gap-8 px-4 py-3 sm:px-6">
        <span class="text-lg font-semibold tracking-tight">NewsAgent</span>
        <nav class="flex gap-1">
          <router-link
            to="/admin"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            Admin
          </router-link>
          <router-link
            to="/preferences"
            class="rounded-lg px-3 py-1.5 text-sm font-medium text-neutral-600 transition-colors hover:bg-neutral-100 hover:text-neutral-900"
            active-class="bg-neutral-100 text-neutral-900"
          >
            Preferences
          </router-link>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <router-view></router-view>
    </main>
  </div>
</template>
