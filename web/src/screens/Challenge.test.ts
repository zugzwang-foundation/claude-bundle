import { describe, expect, it } from "vitest";
import type { HistoryChat } from "../content/types";
import {
  formatSeconds,
  groupByMonth,
  pickTarget,
  stem,
  titleMatches,
  titleOverlap,
  words,
} from "./Challenge";

function chat(partial: Partial<HistoryChat> & { id: string }): HistoryChat {
  return {
    libraryId: partial.id,
    title: "Untitled",
    question: "",
    reply: "",
    paraphrase: "",
    interest: "sample",
    threadId: null,
    date: "2026-05-01T09:00:00.000Z",
    mine: true,
    ...partial,
  };
}

describe("titleMatches", () => {
  it("ignores case and matches inside words", () => {
    expect(titleMatches("Castling early", "CAST")).toBe(true);
    expect(titleMatches("Castling early", "ear")).toBe(true);
    expect(titleMatches("Castling early", "late")).toBe(false);
  });

  it("needs every typed word, in any order", () => {
    expect(titleMatches("A 20-week half marathon plan", "marathon half")).toBe(true);
    expect(titleMatches("A 20-week half marathon plan", "20 week")).toBe(true);
    expect(titleMatches("A 20-week half marathon plan", "marathon shoes")).toBe(false);
  });

  it("treats punctuation, apostrophes and accents as noise", () => {
    expect(titleMatches("First budget that doesn't suck", "doesnt")).toBe(true);
    expect(titleMatches("Café etiquette abroad", "cafe")).toBe(true);
    expect(titleMatches("Anything", "   ")).toBe(true);
    expect(words("  , . ")).toEqual([]);
  });
});

describe("pickTarget", () => {
  it("prefers the own chat whose paraphrase shares the fewest title words", () => {
    const easy = chat({
      id: "easy",
      title: "Chess basics for a beginner",
      paraphrase: "chess basics when you are a beginner",
      date: "2026-01-01T09:00:00.000Z",
    });
    const hard = chat({
      id: "hard",
      title: "Castling early",
      paraphrase: "the right moment to tuck the king away behind its pawns",
      date: "2026-03-01T09:00:00.000Z",
    });
    expect(titleOverlap(easy.title, easy.paraphrase)).toBeGreaterThan(
      titleOverlap(hard.title, hard.paraphrase),
    );
    expect(pickTarget([easy, hard], [])?.id).toBe("hard");
  });

  it("breaks ties towards the older chat and falls back to the history", () => {
    const older = chat({
      id: "older",
      title: "One",
      paraphrase: "x",
      date: "2026-01-01T00:00:00Z",
    });
    const newer = chat({
      id: "newer",
      title: "Two",
      paraphrase: "y",
      date: "2026-02-01T00:00:00Z",
    });
    expect(pickTarget([newer, older], [])?.id).toBe("older");
    const library = chat({ id: "lib", mine: false, title: "Three", paraphrase: "z" });
    const later = chat({ id: "later-lib2", mine: false, title: "Four", paraphrase: "w" });
    expect(pickTarget([], [later, library])?.id).toBe("lib");
    expect(pickTarget([], [])).toBeNull();
  });

  it("stems plurals and endings so shared topics count", () => {
    expect(stem("openings")).toBe("open");
    expect(stem("opening")).toBe("open");
    expect(stem("pieces")).toBe("piece");
    expect(stem("studies")).toBe("study");
    expect(stem("glass")).toBe("glass");
    expect(stem("trainers")).toBe(stem("trainer"));
    expect(titleOverlap("A simple opening repertoire", "openings I can rely on")).toBe(1);
  });
});

describe("formatSeconds and groupByMonth", () => {
  it("formats minutes and seconds", () => {
    expect(formatSeconds(0)).toBe("0:00");
    expect(formatSeconds(7_400)).toBe("0:07");
    expect(formatSeconds(62_000)).toBe("1:02");
    expect(formatSeconds(-5)).toBe("0:00");
  });

  it("groups consecutive chats by calendar month, keeping order", () => {
    const chats = [
      chat({ id: "a", date: "2026-10-20T10:00:00.000Z" }),
      chat({ id: "b", date: "2026-10-02T10:00:00.000Z" }),
      chat({ id: "c", date: "2026-09-28T10:00:00.000Z" }),
    ];
    const groups = groupByMonth(chats);
    expect(groups.map((g) => g.chats.map((c) => c.id))).toEqual([["a", "b"], ["c"]]);
    expect(groups[0]?.label).toMatch(/October 2026/);
  });
});
