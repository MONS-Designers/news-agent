import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import AdminView from "@/views/AdminView.vue";
import PreferencesView from "@/views/PreferencesView.vue";

const routes: RouteRecordRaw[] = [
  {
    path: "/admin",
    name: "Admin",
    component: AdminView,
  },
  {
    path: "/preferences",
    name: "Preferences",
    component: PreferencesView,
  },
  {
    path: "/",
    redirect: "/admin",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
