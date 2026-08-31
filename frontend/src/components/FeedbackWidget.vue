<template>
  <div v-if="thanks" class="fixed bottom-5 end-5 z-30 rounded-xl bg-neutral-900 px-4 py-3 text-sm text-white shadow-lg">
    תודה. זה בדיוק מה שעוזר לנו.
  </div>

  <template v-else>
    <button
      v-if="!open"
      type="button"
      @click="open = true"
      class="fixed bottom-5 end-5 z-30 rounded-full bg-neutral-900 px-5 py-3 text-sm font-medium text-white shadow-lg transition-transform hover:-translate-y-0.5"
    >
      יש לך מה להגיד? 💬
    </button>

    <div
      v-else
      class="fixed bottom-5 end-5 z-30 w-[min(22rem,calc(100vw-2.5rem))] rounded-2xl border border-neutral-200 bg-white p-4 shadow-xl"
    >
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-sm font-semibold text-neutral-900">איך זה מרגיש עד עכשיו?</p>
          <p class="mt-0.5 text-xs text-neutral-500">גרסת בטא. הדעה שלך משנה כאן דברים.</p>
        </div>
        <button
          type="button"
          @click="close"
          aria-label="סגירה"
          class="-me-1 -mt-1 rounded-lg px-2 py-1 text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700"
        >
          ✕
        </button>
      </div>

      <div class="mt-3 flex justify-center gap-1.5" role="radiogroup" aria-label="דירוג">
        <button
          v-for="(face, i) in RATING_FACES"
          :key="i"
          type="button"
          @click="rating = rating === i + 1 ? null : i + 1"
          :aria-pressed="rating === i + 1"
          :aria-label="face.label"
          class="rounded-xl p-1.5 text-2xl leading-none transition-all"
          :class="rating === i + 1 ? 'scale-125' : 'opacity-40 hover:opacity-70'"
        >
          {{ face.emoji }}
        </button>
      </div>

      <textarea
        v-model="text"
        rows="3"
        maxlength="2000"
        placeholder="חשוב לנו לשמוע מה דעתך ואיך אנחנו יכולים להשתפר."
        class="mt-3 w-full resize-none rounded-xl border border-neutral-200 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-400 focus:outline-none"
      ></textarea>

      <p v-if="error" class="mt-2 text-xs text-red-600">{{ error }}</p>

      <button
        type="button"
        @click="submit"
        :disabled="saving || isEmpty"
        class="mt-2 w-full rounded-xl bg-neutral-900 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:bg-neutral-300"
      >
        {{ saving ? "שולח…" : "שליחה" }}
      </button>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { submitFeedback } from "@/api/client";

const route = useRoute();
const router = useRouter();

// Faces read faster than an abstract 1-5 scale - the point is to help
// someone pick, not to make them translate a number into a feeling first.
const RATING_FACES = [
  { emoji: "😞", label: "1 מתוך 5: גרוע" },
  { emoji: "🙁", label: "2 מתוך 5: לא ממש" },
  { emoji: "😐", label: "3 מתוך 5: בסדר" },
  { emoji: "🙂", label: "4 מתוך 5: טוב" },
  { emoji: "😄", label: "5 מתוך 5: מעולה" },
];

const open = ref(false);
const thanks = ref(false);
const rating = ref<number | null>(null);
const text = ref("");
const saving = ref(false);
const error = ref("");

const isEmpty = computed(() => rating.value === null && text.value.trim() === "");

// The digest's "say it in words" link lands here with ?feedback=open. The
// query is consumed immediately so a refresh doesn't replay it.
onMounted(() => {
  const flag = route.query.feedback;
  if (flag === "open") open.value = true;
  if (flag) {
    const query = { ...route.query };
    delete query.feedback;
    void router.replace({ query });
  }
});

function close() {
  open.value = false;
  error.value = "";
}

async function submit() {
  saving.value = true;
  error.value = "";
  try {
    await submitFeedback(rating.value, text.value.trim());
    open.value = false;
    thanks.value = true;
    rating.value = null;
    text.value = "";
  } catch {
    error.value = "השליחה נכשלה. אפשר לנסות שוב.";
  } finally {
    saving.value = false;
  }
}
</script>
