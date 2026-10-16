import { describe, expect, it } from "vitest";
import type { BundleStep, BundlingResult } from "../sorter/bundler";
import { formatDuration, latencyStats, locate, moversAt, planReplay } from "./Reveal";

function step(partial: Partial<BundleStep> & Pick<BundleStep, "chatId" | "action">): BundleStep {
  return {
    targetId: null,
    createdBundleId: null,
    probability: 0,
    probabilities: {},
    ms: 1,
    ...partial,
  };
}

/** a is left loose; b pairs with a into bundle-1; c files into bundle-1; d is left loose. */
const result: BundlingResult = {
  bundles: [{ id: "bundle-1", name: "A", chatIds: ["a", "b", "c"], vector: new Float32Array() }],
  loose: ["d"],
  placements: {
    a: { chatId: "a", bundleId: "bundle-1", probability: 0.1, action: "leave", suggested: false },
    b: { chatId: "b", bundleId: "bundle-1", probability: 0.9, action: "file", suggested: false },
    c: { chatId: "c", bundleId: "bundle-1", probability: 0.6, action: "suggest", suggested: true },
    d: { chatId: "d", bundleId: null, probability: 0.2, action: "leave", suggested: false },
  },
  steps: [
    step({ chatId: "a", action: "leave", probability: 0.1, ms: 1 }),
    step({
      chatId: "b",
      action: "file",
      targetId: "a",
      createdBundleId: "bundle-1",
      probability: 0.9,
      ms: 2,
    }),
    step({ chatId: "c", action: "suggest", targetId: "bundle-1", probability: 0.6, ms: 3 }),
    step({ chatId: "d", action: "leave", probability: 0.2, ms: 10 }),
  ],
  embedMs: 100,
  decisionMs: 16,
};

describe("formatDuration", () => {
  it("rounds to whole seconds under a minute", () => {
    expect(formatDuration(6_000)).toBe("6 s");
    expect(formatDuration(48_400)).toBe("48 s");
    expect(formatDuration(59_400)).toBe("59 s");
  });
  it("uses mm:ss from a minute up", () => {
    expect(formatDuration(60_000)).toBe("01:00");
    expect(formatDuration(72_000)).toBe("01:12");
    expect(formatDuration(600_000)).toBe("10:00");
  });
  it("never shows zero", () => {
    expect(formatDuration(0)).toBe("<1 s");
    expect(formatDuration(400)).toBe("<1 s");
    expect(formatDuration(-5)).toBe("<1 s");
  });
});

describe("planReplay and locate", () => {
  const plan = planReplay(result);

  it("keeps the sorter's order and remembers when each bundle began", () => {
    expect(plan.order).toEqual(["a", "b", "c", "d"]);
    expect(plan.bundleAt.get("bundle-1")).toBe(1);
  });

  it("leaves everything unsorted before the first step", () => {
    for (const id of plan.order) expect(locate(plan, id, 0)).toEqual({ where: "unsorted" });
  });

  it("keeps a chat loose until a later chat forms a bundle with it", () => {
    expect(locate(plan, "a", 1)).toEqual({ where: "loose" });
    expect(locate(plan, "a", 2)).toEqual({ where: "bundle", bundleId: "bundle-1" });
    expect(locate(plan, "b", 1)).toEqual({ where: "unsorted" });
    expect(locate(plan, "b", 2)).toEqual({ where: "bundle", bundleId: "bundle-1" });
  });

  it("files into an existing bundle and leaves the rest loose", () => {
    expect(locate(plan, "c", 3)).toEqual({ where: "bundle", bundleId: "bundle-1" });
    expect(locate(plan, "d", 4)).toEqual({ where: "loose" });
    expect(locate(plan, "unknown", 4)).toEqual({ where: "unsorted" });
  });

  it("shows the founding pair the probability of the match that formed the bundle", () => {
    expect(plan.moves.get("a")?.probability).toBe(0.9);
    expect(plan.moves.get("b")?.probability).toBe(0.9);
    expect(plan.moves.get("c")).toMatchObject({ probability: 0.6, suggested: true });
    expect(plan.moves.get("d")).toMatchObject({ bundleId: null, suggested: false });
  });
});

describe("moversAt", () => {
  it("moves one chat, or two when a bundle is formed", () => {
    expect(moversAt(result, 0)).toEqual(["a"]);
    expect(moversAt(result, 1)).toEqual(["b", "a"]);
    expect(moversAt(result, 2)).toEqual(["c"]);
    expect(moversAt(result, 9)).toEqual([]);
  });
});

describe("latencyStats", () => {
  it("summarises per-decision times", () => {
    const stats = latencyStats(result);
    expect(stats.count).toBe(4);
    expect(stats.meanMs).toBe(4);
    expect(stats.maxMs).toBe(10);
    expect(stats.p95Ms).toBe(10);
    expect(stats.embedMs).toBe(100);
    expect(stats.decisionMs).toBe(16);
  });
  it("copes with no decisions", () => {
    const stats = latencyStats({ ...result, steps: [] });
    expect(stats).toMatchObject({ count: 0, meanMs: 0, maxMs: 0, p95Ms: 0 });
  });
});
