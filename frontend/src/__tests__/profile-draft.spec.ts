import { describe, it, expect, beforeEach } from "vitest";
import { profileDraft, preferencesDraft, initProfileDraft, patchProfileDraft } from "../profile-draft";
import type { Profile, TopicPreference } from "@/api/client";

const PROFILE: Profile = {
  field_name: "פיתוח",
  role_name: "מפתח",
  experience_bucket: "3-5",
  interest_free_text: "בינה מלאכותית",
  topics_stale_at: null,
};
const PREFS: TopicPreference[] = [{ topic_id: 1, name: "AI", subscribed: true }];

beforeEach(() => {
  profileDraft.value = null;
  preferencesDraft.value = [];
});

describe("profile-draft", () => {
  it("starts with null profile and empty preferences", () => {
    expect(profileDraft.value).toBeNull();
    expect(preferencesDraft.value).toEqual([]);
  });

  it("initProfileDraft seeds both refs", () => {
    initProfileDraft(PROFILE, PREFS);
    expect(profileDraft.value).toEqual(PROFILE);
    expect(preferencesDraft.value).toEqual(PREFS);
  });

  it("patchProfileDraft merges fields into an already-seeded profile", () => {
    initProfileDraft(PROFILE, PREFS);
    patchProfileDraft({ field_name: "עיצוב", role_name: "מעצב" });
    expect(profileDraft.value).toEqual({
      ...PROFILE,
      field_name: "עיצוב",
      role_name: "מעצב",
    });
    // Unpatched fields and preferences are untouched.
    expect(profileDraft.value?.interest_free_text).toBe("בינה מלאכותית");
    expect(preferencesDraft.value).toEqual(PREFS);
  });

  it("patchProfileDraft is a no-op when profileDraft is still null", () => {
    patchProfileDraft({ field_name: "עיצוב" });
    expect(profileDraft.value).toBeNull();
  });
});
