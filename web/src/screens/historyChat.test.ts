import { describe, expect, it } from "vitest";
import { groupByMonth } from "../components/Sidebar";
import { assemble } from "../content/assemble";
import sample from "../content/fixtures/sample.json";
import type { HistoryChat, LibraryInterest } from "../content/types";
import { MAX_READY_QUESTIONS, ownChat, pickReadyQuestions, TYPED_REPLY } from "./Chat";
import { fallbackPersonality, historyNote, holdBackLastChats, withArticle } from "./History";

const NOW = new Date("2026-10-16T12:00:00Z");

/** Three interests cloned from the fixture (3 threads of 8 chats, 6 one-offs each). */
function library(): LibraryInterest[] {
  return ["alpha", "bravo", "charlie"].map((name) => {
    const clone = JSON.parse(
      JSON.stringify(sample).replaceAll("sample-", `${name}-`),
    ) as LibraryInterest;
    return { ...clone, interest: name };
  });
}

describe("holdBackLastChats", () => {
  it("drops the last chat of each thread of the chosen interests only", () => {
    const held = holdBackLastChats(library(), ["alpha"]);
    const alpha = held.find((e) => e.interest === "alpha");
    const bravo = held.find((e) => e.interest === "bravo");
    expect(alpha?.threads.every((t) => t.chats.length === 7)).toBe(true);
    expect(alpha?.threads[0]?.chats.at(-1)?.id).toBe("alpha-t1-c7");
    expect(bravo?.threads.every((t) => t.chats.length === 8)).toBe(true);
    expect(alpha?.oneOffs).toHaveLength(6);
  });

  it("does not mutate the library", () => {
    const lib = library();
    holdBackLastChats(lib, ["alpha", "bravo"]);
    expect(lib[0]?.threads[0]?.chats).toHaveLength(8);
  });
});

describe("pickReadyQuestions", () => {
  it("offers the held-back chat of five different threads across the interests", () => {
    const lib = library();
    const interests = ["alpha", "bravo", "charlie"];
    const history = assemble(interests, 7, {
      now: NOW,
      library: holdBackLastChats(lib, interests),
    });
    const used = new Set(history.map((c) => c.libraryId));
    const picks = pickReadyQuestions(lib, interests, used, 7);
    expect(picks).toHaveLength(MAX_READY_QUESTIONS);
    expect(new Set(picks.map((p) => p.threadId)).size).toBe(MAX_READY_QUESTIONS);
    expect(picks.every((p) => p.chat.id.endsWith("-c8"))).toBe(true);
    expect(picks.slice(0, 3).map((p) => p.interest)).toEqual(interests);
  });

  it("is deterministic for a seed and skips threads with nothing left", () => {
    const lib = library();
    const used = new Set(lib.flatMap((e) => e.threads.flatMap((t) => t.chats.map((c) => c.id))));
    expect(pickReadyQuestions(lib, ["alpha"], used, 1)).toEqual([]);
    const a = pickReadyQuestions(lib, ["alpha", "bravo"], new Set(), 3);
    const b = pickReadyQuestions(lib, ["alpha", "bravo"], new Set(), 3);
    expect(a).toEqual(b);
    expect(a.every((p) => p.chat.id.endsWith("-c1"))).toBe(true);
  });

  it("returns nothing for an empty library or unknown interests", () => {
    expect(pickReadyQuestions([], ["alpha"], new Set(), 1)).toEqual([]);
    expect(pickReadyQuestions(library(), ["zulu"], new Set(), 1)).toEqual([]);
  });
});

describe("ownChat", () => {
  it("is the visitor's, dated minutes after the fixed now", () => {
    const lib = library();
    const [pick] = pickReadyQuestions(lib, ["alpha"], new Set(), 1);
    if (!pick) throw new Error("expected a pick");
    const chat = ownChat(pick, NOW.toISOString(), 2);
    expect(chat.mine).toBe(true);
    expect(chat.libraryId).toBe(pick.chat.id);
    expect(chat.threadId).toBe(pick.threadId);
    expect(Date.parse(chat.date) - NOW.getTime()).toBe(4 * 60_000);
  });
});

describe("groupByMonth", () => {
  it("groups newest first and keeps every chat", () => {
    const lib = library();
    const chats = assemble(["alpha", "bravo", "charlie"], 11, { now: NOW, library: lib });
    const groups = groupByMonth(chats);
    expect(groups.reduce((n, g) => n + g.chats.length, 0)).toBe(chats.length);
    expect(groups.length).toBeGreaterThanOrEqual(8);
    expect(groups.length).toBeLessThanOrEqual(10);
    for (let i = 1; i < groups.length; i += 1) {
      const a = groups[i - 1]?.chats[0]?.date ?? "";
      const b = groups[i]?.chats[0]?.date ?? "";
      expect(Date.parse(a)).toBeGreaterThan(Date.parse(b));
    }
    expect(groups[0]?.label).toMatch(/^October 2026$/);
  });

  it("labels months in English and tolerates an empty list", () => {
    const chat: HistoryChat = {
      id: "x",
      libraryId: "x",
      title: "t",
      question: "q",
      reply: "r",
      paraphrase: "p",
      interest: "alpha",
      threadId: null,
      date: "2026-02-03T10:00:00Z",
      mine: false,
    };
    expect(groupByMonth([chat])[0]?.label).toBe("February 2026");
    expect(groupByMonth([])).toEqual([]);
  });
});

describe("copy", () => {
  it("chooses the article and words the note", () => {
    expect(withArticle("Weekend Explorer")).toBe("a Weekend Explorer");
    expect(withArticle("Early Riser")).toBe("an Early Riser");
    expect(historyNote("Weekend Explorer")).toBe(
      "Nine months of chats, written for a Weekend Explorer",
    );
    expect(TYPED_REPLY).toMatch(/ready-made/);
  });

  it("falls back to the first three interests", () => {
    expect(fallbackPersonality(library()).interests).toEqual(["alpha", "bravo", "charlie"]);
    expect(fallbackPersonality([]).interests).toEqual([]);
  });
});
