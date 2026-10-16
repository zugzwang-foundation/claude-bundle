import { describe, expect, it } from "vitest";
import {
  buildResult,
  chooseInterests,
  choosePersonalityType,
  INTEREST_LABELS,
  INTERESTS,
  type Interest,
  indefiniteArticle,
  MAX_INTERESTS,
  MIN_INTERESTS,
  PERSONALITY_TYPES,
  QUESTIONS,
  scoreAnswers,
} from "./quiz";

const LIBRARY_INTERESTS = [
  "fitness",
  "travel",
  "food",
  "money",
  "work",
  "study",
  "music",
  "home",
  "pets",
  "tech",
  "health",
  "parenting",
];

describe("quiz content", () => {
  it("uses exactly the library's twelve interests", () => {
    expect([...INTERESTS]).toEqual(LIBRARY_INTERESTS);
    for (const interest of INTERESTS) expect(INTEREST_LABELS[interest]).toBeTruthy();
  });

  it("has seven questions of four options with unique ids and valid weights", () => {
    expect(QUESTIONS).toHaveLength(7);
    expect(new Set(QUESTIONS.map((q) => q.id)).size).toBe(QUESTIONS.length);
    for (const question of QUESTIONS) {
      expect(question.options).toHaveLength(4);
      expect(new Set(question.options.map((o) => o.id)).size).toBe(4);
      for (const option of question.options) {
        const entries = Object.entries(option.weights);
        expect(entries.length).toBeGreaterThan(0);
        for (const [interest, weight] of entries) {
          expect(LIBRARY_INTERESTS).toContain(interest);
          expect(weight).toBeGreaterThan(0);
        }
      }
    }
  });

  it("gives every interest a main tap somewhere", () => {
    for (const interest of INTERESTS) {
      const mainTaps = QUESTIONS.flatMap((q) => q.options).filter(
        (o) => (o.weights[interest] ?? 0) >= 3,
      );
      expect(mainTaps.length, interest).toBeGreaterThanOrEqual(2);
    }
  });

  it("has 8 to 12 original types that cover every interest at least twice", () => {
    expect(PERSONALITY_TYPES.length).toBeGreaterThanOrEqual(8);
    expect(PERSONALITY_TYPES.length).toBeLessThanOrEqual(12);
    expect(new Set(PERSONALITY_TYPES.map((t) => t.id)).size).toBe(PERSONALITY_TYPES.length);
    expect(new Set(PERSONALITY_TYPES.map((t) => t.name)).size).toBe(PERSONALITY_TYPES.length);
    for (const interest of INTERESTS) {
      const count = PERSONALITY_TYPES.filter((t) => t.interests.includes(interest)).length;
      expect(count, interest).toBeGreaterThanOrEqual(2);
    }
    for (const type of PERSONALITY_TYPES) expect(type.tagline.length).toBeGreaterThan(10);
  });
});

describe("quiz scoring", () => {
  it("sums the weights of the answered options and ignores unknown ids", () => {
    const scores = scoreAnswers({ q1: "a", q2: "nope", zzz: "a" });
    expect(scores.fitness).toBe(3);
    expect(scores.health).toBe(1);
    expect(scores.travel).toBe(0);
  });

  it("always chooses between three and five interests", () => {
    const seen = new Set<number>();
    for (const answers of allAnswerSets(400)) {
      const interests = chooseInterests(scoreAnswers(answers));
      expect(interests.length).toBeGreaterThanOrEqual(MIN_INTERESTS);
      expect(interests.length).toBeLessThanOrEqual(MAX_INTERESTS);
      expect(new Set(interests).size).toBe(interests.length);
      seen.add(interests.length);
    }
    expect(seen.size).toBeGreaterThan(1);
  });

  it("puts the strongest interest first", () => {
    // Every fitness-leaning answer.
    const answers = { q1: "a", q3: "c", q5: "a", q7: "a" };
    const interests = chooseInterests(scoreAnswers(answers));
    expect(interests[0]).toBe("fitness");
  });

  it("picks a type that shares the top interest and is deterministic", () => {
    for (const answers of allAnswerSets(200)) {
      const first = buildResult(answers);
      const second = buildResult(answers);
      expect(second.type.id).toBe(first.type.id);
      expect(second.interests).toEqual(first.interests);
      const top = first.interests[0] as Interest;
      const shared = first.type.interests.some((i) => first.interests.includes(i));
      expect(shared, `${first.type.name} vs ${top}`).toBe(true);
    }
  });

  it("can reach every type", () => {
    const reached = new Set<string>();
    for (const type of PERSONALITY_TYPES) {
      reached.add(choosePersonalityType(type.interests).id);
    }
    expect(reached.size).toBe(PERSONALITY_TYPES.length);
  });

  it("falls back to the first type when nothing was answered", () => {
    const result = buildResult({});
    expect(result.interests).toHaveLength(MIN_INTERESTS);
    expect(result.type).toBe(PERSONALITY_TYPES[0]);
  });

  it("chooses the article by the first letter", () => {
    expect(indefiniteArticle("Weekend Explorer")).toBe("a");
    expect(indefiniteArticle("Early Riser")).toBe("an");
  });
});

/** A spread of answer sets: every single column, then a deterministic pseudo-random sample. */
function* allAnswerSets(count: number): Generator<Record<string, string>> {
  for (const letter of ["a", "b", "c", "d"]) {
    yield Object.fromEntries(QUESTIONS.map((q) => [q.id, letter]));
  }
  let seed = 7;
  for (let n = 0; n < count; n += 1) {
    const answers: Record<string, string> = {};
    for (const question of QUESTIONS) {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      const option = question.options[seed % question.options.length];
      if (option) answers[question.id] = option.id;
    }
    yield answers;
  }
}
