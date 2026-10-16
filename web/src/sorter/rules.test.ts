import { describe, expect, it } from "vitest";
import { decide, topCandidate } from "./rules";

// Fixed cut-offs: the rules are threshold logic and must not move when calibration.json is recalibrated.
const calibration = { fileCutoff: 0.85, suggestCutoff: 0.55 };

describe("decide", () => {
  it("files at or above the file cutoff", () => {
    expect(decide({ a: 0.85, none: 0.15 }, calibration)).toMatchObject({
      action: "file",
      target: "a",
    });
    expect(decide({ a: 0.95, b: 0.03, none: 0.02 }, calibration).action).toBe("file");
  });

  it("suggests between the two cutoffs, including exactly at the suggest cutoff", () => {
    expect(decide({ a: 0.8499, none: 0.1501 }, calibration)).toMatchObject({
      action: "suggest",
      target: "a",
    });
    expect(decide({ a: 0.55, none: 0.45 }, calibration)).toMatchObject({
      action: "suggest",
      target: "a",
    });
  });

  it("leaves below the suggest cutoff, with no target", () => {
    expect(decide({ a: 0.5499, none: 0.4501 }, calibration)).toEqual({
      probabilities: { a: 0.5499, none: 0.4501 },
      action: "leave",
      target: null,
    });
  });

  it("never picks none as the top, even when it is the largest", () => {
    const d = decide({ none: 0.39, a: 0.6, b: 0.01 }, calibration);
    expect(d).toMatchObject({ action: "suggest", target: "a" });
  });

  it("leaves when there are no candidates", () => {
    expect(decide({ none: 1 }, calibration)).toMatchObject({ action: "leave", target: null });
    expect(decide({}, calibration)).toMatchObject({ action: "leave", target: null });
  });

  it("breaks ties by first occurrence", () => {
    expect(decide({ a: 0.5, b: 0.5 }, { fileCutoff: 0.9, suggestCutoff: 0.5 }).target).toBe("a");
  });

  it("respects custom cutoffs", () => {
    const strict = { fileCutoff: 0.99, suggestCutoff: 0.9 };
    expect(decide({ a: 0.95, none: 0.05 }, strict).action).toBe("suggest");
    expect(decide({ a: 0.85, none: 0.15 }, strict).action).toBe("leave");
  });
});

describe("topCandidate", () => {
  it("returns the best non-none candidate or null", () => {
    expect(topCandidate({ a: 0.2, b: 0.5, none: 0.3 })).toMatchObject({ id: "b" });
    expect(topCandidate({ none: 1 })).toBeNull();
  });
});
