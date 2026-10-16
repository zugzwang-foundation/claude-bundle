import { describe, expect, it } from "vitest";
import {
  bundleChatIdsFor,
  fillContinuation,
  fillContinuationParts,
  pickContinuation,
  SLOT_PATTERN,
} from "./continuation";
import sample from "./fixtures/sample.json";
import type { HistoryChat, LibraryInterest, LibraryThread } from "./types";

const library = [sample as LibraryInterest];
const chess = sample.threads[0] as LibraryThread;
const gameNight = sample.threads[1] as LibraryThread;

/** The thread's chats as history entries, one per position, dated a week apart. */
function historyOf(thread: LibraryThread, mineAt: number | null = null): HistoryChat[] {
  return thread.chats.map((chat, index) => ({
    id: mineAt === index ? `mine-${chat.id}` : chat.id,
    libraryId: chat.id,
    title: chat.title,
    question: chat.question,
    reply: chat.reply,
    paraphrase: chat.paraphrase,
    interest: sample.interest,
    threadId: thread.id,
    date: new Date(Date.UTC(2026, 1, 1 + index * 7, 9)).toISOString(),
    mine: mineAt === index,
  }));
}

const ids = (chats: HistoryChat[], ...positions: number[]) =>
  new Set(positions.map((n) => (chats[n - 1] as HistoryChat).id));

describe("fillContinuation: slot in the bundle", () => {
  const chats = historyOf(chess);

  it("replaces every slot with the N-th chat's title when all are in the bundle", () => {
    const out = fillContinuation(chess.continuation.reply, chats, ids(chats, 3, 4, 5));
    expect(out).toBe(
      "Keep the habits that got you here: the blunder check from Blunder checks, castling early as in Castling early, and the small repertoire from A simple opening repertoire. Add fifteen minutes of tactics a day and review every loss the way we discussed. Ratings climb in steps, so expect plateaus.",
    );
    expect(out).not.toMatch(SLOT_PATTERN);
  });

  it("keeps the parts in order and marks the filled titles", () => {
    const parts = fillContinuationParts(
      gameNight.continuation.reply,
      historyOf(gameNight),
      ids(historyOf(gameNight), 1, 2, 3),
    );
    const titles = parts.filter((part) => part.kind === "title");
    expect(titles.map((part) => part.text)).toEqual([
      "Games for six people",
      "Teaching rules fast",
      "Snacks that keep cards clean",
    ]);
    expect(titles.map((part) => (part.kind === "title" ? part.chatId : ""))).toEqual([
      "sample-t2-c1",
      "sample-t2-c2",
      "sample-t2-c3",
    ]);
    expect(parts.map((part) => part.text).join("")).toBe(
      fillContinuation(
        gameNight.continuation.reply,
        historyOf(gameNight),
        ids(historyOf(gameNight), 1, 2, 3),
      ),
    );
    expect(parts[0]).toEqual({
      kind: "text",
      text: "Lean on what already works: the six-player picks from ",
    });
  });

  it("checks membership by history id, so the visitor's own copy of a chat counts", () => {
    const mine = historyOf(chess, 4);
    const bundle = new Set(["mine-sample-t1-c5"]);
    expect(fillContinuation("Remember {{chat:5}}.", mine, bundle)).toBe("Remember Blunder checks.");
    expect(fillContinuation("Remember {{chat:5}}.", historyOf(chess), bundle)).toBe("Remember.");
  });
});

describe("fillContinuation: slot's chat not in the bundle, another one is", () => {
  const chats = historyOf(chess);

  it("substitutes the nearest unused in-bundle chat of the same thread", () => {
    // Chat 5 is missing; chats 3, 4 and 6 are present. 4 and 3 are claimed by their own slots, so 6 stands in.
    const out = fillContinuation(chess.continuation.reply, chats, ids(chats, 3, 4, 6));
    expect(out).toContain("the blunder check from Rook endgames");
    expect(out).toContain("castling early as in Castling early");
    expect(out).toContain("the small repertoire from A simple opening repertoire");
  });

  it("never reuses a title another slot already filled, even when that slot comes later", () => {
    // Only 3 and 4 are in the bundle: slot 5 cannot take them, so it is dropped rather than repeated.
    const out = fillContinuation(chess.continuation.reply, chats, ids(chats, 3, 4));
    const matches = out.match(/Castling early|A simple opening repertoire/g) ?? [];
    expect(matches).toHaveLength(2);
    expect(out).toContain("the blunder check, castling early as in Castling early");
  });

  it("treats an out-of-range or unreadable position as a slot to substitute", () => {
    expect(fillContinuation("Start with {{chat:9}}.", chats, ids(chats, 2))).toBe(
      "Start with Controlling the centre.",
    );
    expect(fillContinuation("Start with {{chat:0}}.", chats, ids(chats, 7))).toBe(
      "Start with Reviewing lost games.",
    );
    expect(fillContinuation("Start with {{chat:x}}.", chats, ids(chats, 1))).toBe(
      "Start with Chess basics for a beginner.",
    );
  });
});

describe("fillContinuation: no in-bundle chat for the slot", () => {
  const chats = historyOf(chess);
  const none = new Set<string>();

  it("drops the slot and tidies the sentence", () => {
    const out = fillContinuation(chess.continuation.reply, chats, none);
    expect(out).toBe(
      "Keep the habits that got you here: the blunder check, castling early, and the small repertoire. Add fifteen minutes of tactics a day and review every loss the way we discussed. Ratings climb in steps, so expect plateaus.",
    );
  });

  it("removes a dangling conjunction, double spaces and doubled commas", () => {
    expect(fillContinuation("Keep X, Y, and {{chat:3}}.", chats, none)).toBe("Keep X, Y.");
    expect(fillContinuation("Keep {{chat:1}} and {{chat:2}} close.", chats, none)).toBe(
      "Keep close.",
    );
    expect(
      fillContinuation("Use {{chat:1}}, {{chat:2}}, {{chat:3}}, then rest.", chats, none),
    ).toBe("Use, then rest.");
    expect(fillContinuation("{{chat:1}} and {{chat:2}} both matter.", chats, none)).toBe(
      "Both matter.",
    );
    expect(fillContinuation("Think about it (see {{chat:4}}) tonight.", chats, none)).toBe(
      "Think about it tonight.",
    );
    expect(fillContinuation("Keep {{chat:1}}, {{chat:2}} and {{chat:3}} close.", chats, none)).toBe(
      "Keep close.",
    );
  });

  it("drops the conjunction after a bare dropped slot but keeps it after a removed word", () => {
    const two = ids(chats, 2);
    expect(fillContinuation("Keep {{chat:1}} and {{chat:2}} close.", chats, two)).toBe(
      "Keep Controlling the centre close.",
    );
    expect(
      fillContinuation("Try the picks from {{chat:1}} and the trick from {{chat:2}}.", chats, two),
    ).toBe("Try the picks and the trick from Controlling the centre.");
  });

  it("leaves text without slots exactly as written", () => {
    const text = "Nothing to fill here,  not even  double spaces, and no slots.";
    expect(fillContinuation(text, chats, none)).toBe(text);
    expect(fillContinuationParts(text, chats, none)).toEqual([{ kind: "text", text }]);
    expect(fillContinuationParts("", chats, none)).toEqual([]);
  });

  it("fills what it can and drops the rest in one reply", () => {
    const out = fillContinuation(chess.continuation.reply, chats, ids(chats, 4));
    expect(out).toBe(
      "Keep the habits that got you here: the blunder check, castling early, and the small repertoire from A simple opening repertoire. Add fifteen minutes of tactics a day and review every loss the way we discussed. Ratings climb in steps, so expect plateaus.",
    );
  });
});

describe("pickContinuation", () => {
  it("finds the thread of the found chat and returns its continuation and chats in order", () => {
    const history = historyOf(chess, 4);
    const target = history[4] as HistoryChat;
    const picked = pickContinuation(target, library, history);
    expect(picked).not.toBeNull();
    expect(picked?.question).toBe(chess.continuation.question);
    expect(picked?.reply).toBe(chess.continuation.reply);
    expect(picked?.threadId).toBe("sample-t1");
    expect(picked?.topic).toBe("Learning chess from scratch");
    expect(picked?.threadChats.map((chat) => chat.libraryId)).toEqual(chess.chats.map((c) => c.id));
    expect(picked?.threadChats[4]?.id).toBe("mine-sample-t1-c5");
  });

  it("prefers the visitor's own copy of a chat over the library copy", () => {
    const history = [...historyOf(chess), ...historyOf(chess, 2).filter((chat) => chat.mine)];
    const target = history[0] as HistoryChat;
    const picked = pickContinuation(target, library, history);
    expect(picked?.threadChats[2]?.id).toBe("mine-sample-t1-c3");
    expect(picked?.threadChats[2]?.mine).toBe(true);
  });

  it("stands in library chats for positions the history lacks, dated like the target", () => {
    const history = historyOf(gameNight).slice(0, 2);
    const target = history[1] as HistoryChat;
    const picked = pickContinuation(target, library, history);
    expect(picked?.threadChats).toHaveLength(8);
    expect(picked?.threadChats[7]).toMatchObject({
      id: "sample-t2-c8",
      libraryId: "sample-t2-c8",
      interest: "sample",
      threadId: "sample-t2",
      date: target.date,
      mine: false,
    });
  });

  it("works from the library alone and falls back to the chat id when threadId is missing", () => {
    const target: HistoryChat = {
      ...(historyOf(chess)[6] as HistoryChat),
      id: "mine-x",
      threadId: null,
    };
    const picked = pickContinuation(target, library);
    expect(picked?.threadId).toBe("sample-t1");
    expect(picked?.threadChats[6]?.id).toBe("mine-x");
  });

  it("returns null for a one-off or when the library is empty", () => {
    const oneOff: HistoryChat = {
      id: "sample-o1",
      libraryId: "sample-o1",
      title: "Dice probability",
      question: "q",
      reply: "r",
      paraphrase: "p",
      interest: "sample",
      threadId: null,
      date: "2026-05-01T09:00:00.000Z",
      mine: true,
    };
    expect(pickContinuation(oneOff, library)).toBeNull();
    expect(pickContinuation(historyOf(chess)[0] as HistoryChat, [])).toBeNull();
  });
});

describe("bundleChatIdsFor", () => {
  const bundling = {
    bundles: [
      { id: "b1", name: "A", chatIds: ["x", "y", "z"], vector: new Float32Array(0) },
      { id: "b2", name: "B", chatIds: ["p"], vector: new Float32Array(0) },
    ],
  };

  it("gives the ids of the bundle holding the chat", () => {
    expect([...bundleChatIdsFor("y", bundling)].sort()).toEqual(["x", "y", "z"]);
  });

  it("gives just the chat itself when it is loose or nothing is bundled yet", () => {
    expect([...bundleChatIdsFor("loose", bundling)]).toEqual(["loose"]);
    expect([...bundleChatIdsFor("x", null)]).toEqual(["x"]);
  });
});
