import { describe, expect, it } from "vitest";
import {
  assemble,
  HISTORY_MAX,
  HISTORY_MIN,
  HISTORY_SPAN_DAYS,
  mulberry32,
  shuffle,
} from "./assemble";
import sample from "./fixtures/sample.json";
import type { LibraryInterest } from "./types";

const NOW = new Date("2026-10-16T12:00:00Z");
const NAMES = [
  "alpha",
  "bravo",
  "charlie",
  "delta",
  "echo",
  "foxtrot",
  "golf",
  "hotel",
  "india",
  "juliet",
  "kilo",
  "lima",
];

/** Twelve interests cloned from the fixture, each with 3 threads of 8 chats and 6 one-offs. */
function syntheticLibrary(count = 12): LibraryInterest[] {
  return NAMES.slice(0, count).map((name) => {
    const text = JSON.stringify(sample).replaceAll("sample-", `${name}-`);
    const clone = JSON.parse(text) as LibraryInterest;
    return { ...clone, interest: name, label: `${name} things` };
  });
}

describe("mulberry32", () => {
  it("is deterministic and in [0, 1)", () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    for (let i = 0; i < 1000; i += 1) {
      const x = a();
      expect(x).toBe(b());
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThan(1);
    }
  });

  it("differs by seed", () => {
    expect(mulberry32(1)()).not.toBe(mulberry32(2)());
  });
});

describe("shuffle", () => {
  it("keeps every item and does not mutate the input", () => {
    const input = [1, 2, 3, 4, 5, 6, 7, 8];
    const out = shuffle(input, mulberry32(7));
    expect(input).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(out.slice().sort((a, b) => a - b)).toEqual(input);
  });
});

describe("assemble", () => {
  const library = syntheticLibrary();

  it("uses the fixture shape the schema describes", () => {
    expect(sample.threads).toHaveLength(3);
    for (const thread of sample.threads) expect(thread.chats).toHaveLength(8);
    expect(sample.oneOffs).toHaveLength(6);
  });

  it("returns between 100 and 150 chats for 3, 4 and 5 interests", () => {
    for (const count of [3, 4, 5]) {
      const chats = assemble(NAMES.slice(0, count), 11, { now: NOW, library });
      expect(chats.length).toBeGreaterThanOrEqual(HISTORY_MIN);
      expect(chats.length).toBeLessThanOrEqual(HISTORY_MAX);
      expect(chats.length).toBe(Math.max(HISTORY_MIN, count * 30));
    }
  });

  it("includes every chat of the chosen interests and pads only with other one-offs", () => {
    const chosen = ["alpha", "bravo", "charlie"];
    const chats = assemble(chosen, 3, { now: NOW, library });
    const own = chats.filter((chat) => chosen.includes(chat.interest));
    const padding = chats.filter((chat) => !chosen.includes(chat.interest));
    expect(own).toHaveLength(90);
    expect(padding).toHaveLength(10);
    for (const chat of padding) {
      expect(chat.threadId).toBeNull();
      expect(chat.libraryId).toMatch(/-o[1-6]$/);
    }
    const ids = new Set(chats.map((chat) => chat.id));
    expect(ids.size).toBe(chats.length);
  });

  it("is deterministic for a seed and changes with it", () => {
    const a = assemble(["alpha", "bravo", "charlie", "delta"], 5, { now: NOW, library });
    const b = assemble(["alpha", "bravo", "charlie", "delta"], 5, { now: NOW, library });
    const c = assemble(["alpha", "bravo", "charlie", "delta"], 6, { now: NOW, library });
    expect(a).toEqual(b);
    expect(a.map((chat) => chat.date)).not.toEqual(c.map((chat) => chat.date));
  });

  it("keeps every thread in order and spreads chats over nine months ending now", () => {
    const chats = assemble(["alpha", "bravo", "charlie"], 99, { now: NOW, library });
    const earliest = NOW.getTime() - HISTORY_SPAN_DAYS * 24 * 60 * 60 * 1000;
    const dates = chats.map((chat) => Date.parse(chat.date));
    for (const [i, time] of dates.entries()) {
      expect(time).toBeGreaterThanOrEqual(earliest);
      expect(time).toBeLessThanOrEqual(NOW.getTime());
      if (i > 0) expect(time).toBeGreaterThanOrEqual(dates[i - 1] ?? 0);
    }
    const byThread = new Map<string, string[]>();
    for (const chat of chats) {
      if (chat.threadId)
        byThread.set(chat.threadId, [...(byThread.get(chat.threadId) ?? []), chat.libraryId]);
    }
    expect(byThread.size).toBe(9);
    for (const [threadId, ids] of byThread) {
      expect(ids).toEqual(Array.from({ length: 8 }, (_, i) => `${threadId}-c${i + 1}`));
    }
    // Realistic gaps: at least a day between chats of one thread.
    for (const ids of byThread.values()) {
      const times = ids.map((id) => Date.parse(chats.find((c) => c.id === id)?.date ?? ""));
      for (let i = 1; i < times.length; i += 1) {
        expect((times[i] ?? 0) - (times[i - 1] ?? 0)).toBeGreaterThanOrEqual(24 * 60 * 60 * 1000);
      }
    }
    // Spread: the first chat is in the first third, the last in the last third.
    const span = NOW.getTime() - earliest;
    expect((dates[0] ?? 0) - earliest).toBeLessThan(span / 3);
    expect((dates[dates.length - 1] ?? 0) - earliest).toBeGreaterThan((span * 2) / 3);
  });

  it("works with a small library and with none", () => {
    const small = syntheticLibrary(3);
    expect(assemble(["alpha", "bravo", "charlie"], 1, { now: NOW, library: small })).toHaveLength(
      90,
    );
    expect(assemble(["alpha"], 1, { now: NOW, library: [] })).toEqual([]);
    // An unknown interest pads with every one-off in the library: 12 interests x 6.
    expect(assemble(["zulu"], 1, { now: NOW, library })).toHaveLength(72);
  });

  it("marks every chat as not the visitor's own", () => {
    const chats = assemble(["alpha", "bravo", "charlie"], 2, { now: NOW, library });
    expect(chats.every((chat) => chat.mine === false)).toBe(true);
    expect(chats.every((chat) => chat.id === chat.libraryId)).toBe(true);
  });
});
