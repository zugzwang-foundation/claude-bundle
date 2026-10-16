import { describe, expect, it } from "vitest";
import calibration from "./calibration.json";
import {
  candidateVectors,
  cosine,
  l2Normalize,
  meanVector,
  NONE_ID,
  probabilities,
  scoreVectors,
  softmax,
} from "./scoring";

const close = (a: number, b: number, eps = 1e-6) => Math.abs(a - b) < eps;

describe("l2Normalize and cosine", () => {
  it("normalises to unit length and leaves a zero vector alone", () => {
    const v = l2Normalize([3, 4]);
    expect(close(v[0] ?? 0, 0.6)).toBe(true);
    expect(close(v[1] ?? 0, 0.8)).toBe(true);
    expect(Array.from(l2Normalize([0, 0]))).toEqual([0, 0]);
  });

  it("gives 1 for identical, 0 for orthogonal, -1 for opposite and 0 for zero vectors", () => {
    expect(close(cosine([1, 2, 3], [2, 4, 6]), 1)).toBe(true);
    expect(close(cosine([1, 0], [0, 1]), 0)).toBe(true);
    expect(close(cosine([1, 0], [-1, 0]), -1)).toBe(true);
    expect(cosine([0, 0], [1, 1])).toBe(0);
    expect(close(cosine(new Float32Array([1, 1]), [1, 0]), Math.SQRT1_2)).toBe(true);
  });
});

describe("meanVector", () => {
  it("is the normalised mean of its inputs", () => {
    const m = meanVector([
      [1, 0],
      [0, 1],
    ]);
    expect(close(m[0] ?? 0, Math.SQRT1_2)).toBe(true);
    expect(close(m[1] ?? 0, Math.SQRT1_2)).toBe(true);
    expect(meanVector([]).length).toBe(0);
    const single = meanVector([new Float32Array([0, 5])]);
    expect(Array.from(single)).toEqual([0, 1]);
  });
});

describe("softmax", () => {
  it("sums to 1 and sharpens as the temperature drops", () => {
    const warm = softmax({ a: 0.9, b: 0.5, none: 0.3 }, 1);
    const cold = softmax({ a: 0.9, b: 0.5, none: 0.3 }, 0.05);
    const sum = (p: Record<string, number>) => Object.values(p).reduce((s, x) => s + x, 0);
    expect(close(sum(warm), 1)).toBe(true);
    expect(close(sum(cold), 1)).toBe(true);
    expect(cold.a ?? 0).toBeGreaterThan(warm.a ?? 0);
    expect(cold.a ?? 0).toBeGreaterThan(0.99);
    expect(softmax({}, 0.05)).toEqual({});
  });

  it("matches the closed form for two entries", () => {
    const p = softmax({ a: 1, b: 0 }, 1);
    expect(close(p.a ?? 0, 1 / (1 + Math.exp(-1)))).toBe(true);
  });
});

describe("scoreVectors and probabilities", () => {
  const candidates = [
    { id: "b1", vector: l2Normalize([1, 0, 0]) },
    { id: "c7", vector: l2Normalize([0, 1, 0]) },
  ];

  it("scores each candidate by cosine and adds the constant none score", () => {
    const scores = scoreVectors(l2Normalize([1, 1, 0]), candidates, calibration.noneScore);
    expect(close(scores.b1 ?? 0, Math.SQRT1_2)).toBe(true);
    expect(close(scores.c7 ?? 0, Math.SQRT1_2)).toBe(true);
    expect(scores[NONE_ID]).toBe(calibration.noneScore);
  });

  it("sends a perfect match above the file cutoff at the default temperature", () => {
    const p = probabilities(l2Normalize([1, 0.01, 0]), candidates, calibration);
    expect(p.b1 ?? 0).toBeGreaterThan(calibration.fileCutoff);
    expect(Object.keys(p).sort()).toEqual(["b1", "c7", NONE_ID].sort());
  });

  it("leaves an unrelated chat with none when nothing is close", () => {
    const p = probabilities(l2Normalize([0, 0, 1]), candidates, calibration);
    expect(p[NONE_ID] ?? 0).toBeGreaterThan(p.b1 ?? 0);
    expect(p[NONE_ID] ?? 0).toBeGreaterThan(p.c7 ?? 0);
  });
});

describe("candidateVectors", () => {
  const table: Record<string, number[]> = { x: [1, 0], y: [0, 1], z: [1, 1] };
  const vectorOf = (text: string) => table[text];

  it("averages a bundle's examples and uses a loose chat's own text", () => {
    const out = candidateVectors(
      [
        { id: "bundle", kind: "bundle", examples: ["x", "y"] },
        { id: "loose", kind: "loose", text: "z" },
        { id: "missing", kind: "loose", text: "nope" },
        { id: "empty", kind: "bundle", examples: ["nope"] },
      ],
      vectorOf,
    );
    expect(out.map((c) => c.id)).toEqual(["bundle", "loose"]);
    expect(close(out[0]?.vector[0] ?? 0, Math.SQRT1_2)).toBe(true);
    expect(Array.from(out[1]?.vector ?? [])).toEqual([1, 1]);
  });
});
