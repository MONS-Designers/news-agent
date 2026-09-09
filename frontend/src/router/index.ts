import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import AdminView from "@/views/AdminView.vue";
import EngagementView from "@/views/EngagementView.vue";
import HomeView from "@/views/HomeView.vue";
import PreferencesView from "@/views/PreferencesView.vue";
import TaxonomyQueueView from "@/views/TaxonomyQueueView.vue";
import { ensureMe } from "@/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/admin",
    name: "Admin",
    component: AdminView,
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/taxonomy",
    name: "TaxonomyQueue",
    component: TaxonomyQueueView,
    meta: { requiresAdmin: true },
  },
  {
    path: "/admin/engagement",
    name: "Engagement",
    component: EngagementView,
    meta: { requiresAdmin: true },
  },
  {
    path: "/preferences",
    name: "Preferences",
    component: PreferencesView,
    meta: { requiresAuth: true },
  },
  {
    path: "/",
    name: "Home",
    component: HomeView,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.meta.requiresAdmin) {
    const identity = await ensureMe();
    if (!identity?.is_admin) {
      return { path: "/preferences" };
    }
  }
  if (to.meta.requiresAuth) {
    const identity = await ensureMe();
    if (!identity) {
      // An anonymous visitor's home is the landing page. The flag is what
      // lets HomeView say why they ended up there - without it the guard
      // silently swallows the navigation and the click reads as broken.
      return { path: "/", query: { signin: "required" } };
    }
  }
});

export default router;
