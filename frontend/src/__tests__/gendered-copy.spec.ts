// Regression guard for GH #61 (gendered Hebrew copy). Hebrew has no gender-
// neutral second-person present tense, so most offenders fall into one of
// three shapes: the bare pronoun "אתה", the modal "תוכל", or a sentence that
// opens with a masculine imperative verb ("בחר תחום קודם", a bare "אשר"
// button label). See CLAUDE.md's "Gender-neutral Hebrew copy" section for the
// house style (rewrite around the problem - past tense, "יש ל" + infinitive,
// noun phrasing - never slashed forms in prose).
//
// This is a targeted scan, not a parser: it looks for the offending word
// immediately after a quote/tag-open character (approximating "start of a
// string literal or text node"), so it won't flag every occurrence buried
// mid-sentence. It also can't tell imperative "בטל" from some future
// legitimate use of the same letters - if it ever flags a false positive,
// narrow the pattern or add an exemption comment next to it, don't just
// delete the check.
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC_DIR = join(__dirname, "..");

function listVueFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === "__tests__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...listVueFiles(full));
    } else if (entry.endsWith(".vue")) {
      out.push(full);
    }
  }
  return out;
}

// Unambiguous wherever they appear: the masculine 2nd-person pronoun and its
// matching modal. Bounded against Hebrew letters (not \w - that's ASCII-only
// in JS regex) so this doesn't match as a substring of a longer word.
const HEBREW_LETTER = "\\u05D0-\\u05EA";
const ANYWHERE_OFFENDERS = ["אתה", "תוכל"];

// Common bare-imperative (masculine) verbs seen going wrong in this app's UI
// copy - button labels that were just the verb ("אשר", "רענן", "קדם") and
// sentences that opened with one ("בחר תחום קודם", "הקש על נושא..."). Not
// exhaustive, and deliberately excludes words with a common non-imperative
// reading (e.g. "אשר" as the relative pronoun "which/that") to keep false
// positives rare.
const SENTENCE_START_OFFENDERS = [
  "בחר",
  "הקש",
  "בטל",
  "התחבר",
  "פנה",
  "דחה",
  "קדם",
  "רענן",
  "חזור",
  "בוא",
  "לחץ",
  "מחק",
  "שמור",
  "טען",
  "נסה",
  "בדוק",
];

function findAnywhereOffenders(text: string): string[] {
  const hits: string[] = [];
  for (const word of ANYWHERE_OFFENDERS) {
    const re = new RegExp(`(?<![${HEBREW_LETTER}])${word}(?![${HEBREW_LETTER}])`, "g");
    if (re.test(text)) hits.push(word);
  }
  return hits;
}

function findSentenceStartOffenders(text: string): string[] {
  const hits: string[] = [];
  for (const word of SENTENCE_START_OFFENDERS) {
    // Preceded by a quote or tag-close (start of a literal/text node),
    // followed by whitespace, a quote, or a tag-open (end of that word).
    const re = new RegExp(`["'>]\\s*${word}(?=[\\s"'<])`, "g");
    if (re.test(text)) hits.push(word);
  }
  return hits;
}

describe("gendered Hebrew copy (GH #61 regression guard)", () => {
  const files = listVueFiles(SRC_DIR);
  expect(files.length).toBeGreaterThan(0); // sanity check the scan itself found something

  for (const file of files) {
    it(`${file.replace(SRC_DIR, "src")} has no gendered Hebrew copy`, () => {
      const text = readFileSync(file, "utf-8");
      const anywhere = findAnywhereOffenders(text);
      const sentenceStart = findSentenceStartOffenders(text);
      expect(
        [...anywhere.map((w) => `"${w}" (pronoun/modal)`), ...sentenceStart.map((w) => `"${w}" (bare imperative)`)],
      ).toEqual([]);
    });
  }
});
