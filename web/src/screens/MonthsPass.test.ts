import { describe, expect, it } from "vitest";
import sample from "../content/fixtures/sample.json";
import type { HistoryChat, LibraryInterest } from "../content/types";
import {
  anchorDate,
  easeInOut,
  isLater,
  LATER_MAX,
  LATER_MIN,
  LATER_PREFIX,
  LATER_SPAN_DAYS,
  pickLater,
} from "./MonthsPass";

const DAY_MS = 24 * 60 * 60 * 1000;

/** A synthetic library: `count` interests, each with two threads of four chats and six one-offs. */
function makeLibrary(count: number): LibraryInterest[] {
  return Array.from({ length: count }, (_, i) => {
    const interest = `int${i}`;
    const chat = (id: string) => ({
      id,
      title: `Title ${id}`,
      question: `Question ${id}`,
      reply: `Reply ${id}`,
      paraphrase: `Paraphrase ${id}`,
    });
    return {
      interest,
      label: `Interest ${i}`,
      threads: [1, 2].map((t) => ({
        id: `${interest}-t${t}`,
        topic: `Topic ${t}`,
        chats: [1, 2, 3, 4].map((c) => chat(`${interest}-t${t}-c${c}`)),
        continuation: { question: "q", reply: "r" },
      })),
      oneOffs: [1, 2, 3, 4, 5, 6].map((o) => chat(`${interest}-o${o}`)),
    };
  });
}

function own(id: string, date: string): HistoryChat {
  return {
    id,
    libraryId: `lib-${id}`,
    title: id,
    question: "",
    reply: "",
    paraphrase: "",
    interest: "int0",
    threadId: null,
    date,
    mine: true,
  };
}

const AFTER = new Date("2026-10-16T12:00:00.000Z");

describe("pickLater", () => {
  const library = makeLibrary(6);
  const history: HistoryChat[] = [];
  const mine = [own("m1", "2026-10-16T10:00:00.000Z")];

  it("adds between 24 and 40 new chats, all dated after the anchor and inside the span", () => {
    const later = pickLater(["int0", "int1"], history, mine, 7, AFTER, { library });
    expect(later.length).toBeGreaterThanOrEqual(LATER_MIN);
    expect(later.length).toBeLessThanOrEqual(LATER_MAX);
    for (const chat of later) {
      const t = Date.parse(chat.date);
      expect(t).toBeGreaterThan(AFTER.getTime());
      expect(t).toBeLessThanOrEqual(AFTER.getTime() + LATER_SPAN_DAYS * DAY_MS);
      expect(chat.id.startsWith(LATER_PREFIX)).toBe(true);
      expect(isLater(chat)).toBe(true);
      expect(chat.libraryId.startsWith(LATER_PREFIX)).toBe(false);
      expect(chat.mine).toBe(false);
    }
    const dates = later.map((c) => Date.parse(c.date));
    expect(dates).toEqual(dates.slice().sort((a, b) => a - b));
  });

  it("is deterministic for a seed and different for another", () => {
    const a = pickLater(["int0"], history, mine, 3, AFTER, { library });
    const b = pickLater(["int0"], history, mine, 3, AFTER, { library });
    const c = pickLater(["int0"], history, mine, 4, AFTER, { library });
    expect(a).toEqual(b);
    expect(a.map((x) => x.libraryId)).not.toEqual(c.map((x) => x.libraryId));
  });

  it("never repeats a chat already in the history or asked by the visitor", () => {
    const used: HistoryChat[] = library
      .flatMap((entry) => [...entry.oneOffs, ...entry.threads.flatMap((t) => t.chats)])
      .slice(0, 50)
      .map((chat) => ({ ...own(chat.id, "2026-05-01T00:00:00.000Z"), libraryId: chat.id }));
    const later = pickLater(["int0"], used, mine, 11, AFTER, { library });
    const usedIds = new Set(used.map((c) => c.libraryId));
    for (const chat of later) expect(usedIds.has(chat.libraryId)).toBe(false);
    expect(new Set(later.map((c) => c.libraryId)).size).toBe(later.length);
  });

  it("keeps a thread's chats in their original order", () => {
    const later = pickLater([], history, mine, 21, AFTER, { library, min: 40, max: 40 });
    const byThread = new Map<string, number[]>();
    for (const chat of later) {
      if (!chat.threadId) continue;
      const index = Number(chat.libraryId.split("-c")[1]);
      byThread.set(chat.threadId, [...(byThread.get(chat.threadId) ?? []), index]);
    }
    expect(byThread.size).toBeGreaterThan(0);
    for (const indices of byThread.values()) {
      expect(indices).toEqual(indices.slice().sort((a, b) => a - b));
    }
  });

  it("copes with a small library and the fixture", () => {
    const later = pickLater(["sample"], history, mine, 5, AFTER, {
      library: [sample as LibraryInterest],
    });
    const total = sample.threads.reduce((n, t) => n + t.chats.length, 0) + sample.oneOffs.length;
    expect(later.length).toBe(Math.min(total, LATER_MAX) >= LATER_MIN ? later.length : total);
    expect(later.length).toBeLessThanOrEqual(total);
    expect(pickLater([], history, mine, 5, AFTER, { library: [] })).toEqual([]);
  });
});

describe("anchorDate and easing", () => {
  it("anchors on the newest own chat, else the newest non-later history chat", () => {
    const history = [
      { ...own("h1", "2026-09-01T00:00:00.000Z"), mine: false },
      { ...own("later-x", "2026-12-01T00:00:00.000Z"), mine: false },
    ];
    expect(anchorDate(history, [own("m", "2026-10-10T00:00:00.000Z")])?.toISOString()).toBe(
      "2026-10-10T00:00:00.000Z",
    );
    expect(anchorDate(history, [])?.toISOString()).toBe("2026-09-01T00:00:00.000Z");
    expect(anchorDate([], [])).toBeNull();
  });

  it("eases from 0 to 1 and stays monotonic", () => {
    expect(easeInOut(0)).toBe(0);
    expect(easeInOut(1)).toBe(1);
    expect(easeInOut(0.5)).toBeCloseTo(0.5, 5);
    let last = 0;
    for (let i = 1; i <= 20; i += 1) {
      const value = easeInOut(i / 20);
      expect(value).toBeGreaterThanOrEqual(last);
      last = value;
    }
  });
});
