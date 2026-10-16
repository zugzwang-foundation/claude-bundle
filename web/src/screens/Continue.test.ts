import { describe, expect, it } from "vitest";
import sample from "../content/fixtures/sample.json";
import type { HistoryChat, LibraryInterest, LibraryThread } from "../content/types";
import { FALLBACK_CONTINUATION, LOOSE_CONTINUATION, planContinuation } from "./Continue";

const library = [sample as LibraryInterest];
const thread = sample.threads[0] as LibraryThread;

function historyChat(
  libraryId: string,
  threadId: string | null,
  day: number,
  mine = false,
): HistoryChat {
  const source =
    thread.chats.find((c) => c.id === libraryId) ?? sample.oneOffs.find((c) => c.id === libraryId);
  if (!source) throw new Error(`no fixture chat ${libraryId}`);
  return {
    id: mine ? `mine-${libraryId}` : `h-${libraryId}`,
    libraryId,
    title: source.title,
    question: source.question,
    reply: source.reply,
    paraphrase: source.paraphrase,
    interest: sample.interest,
    threadId,
    date: new Date(Date.UTC(2026, 0, day)).toISOString(),
    mine,
  };
}

const c1 = historyChat("sample-t1-c1", "sample-t1", 2);
const c3 = historyChat("sample-t1-c3", "sample-t1", 10);
const c5 = historyChat("sample-t1-c5", "sample-t1", 20);
const oneOff = historyChat("sample-o1", null, 15);
const other = historyChat("sample-o2", null, 16);
const found = historyChat("sample-t1-c8", "sample-t1", 40, true);
const chats = [c1, c3, c5, oneOff, other, found];

function bundleOf(...chatIds: string[]) {
  return { bundles: [{ id: "b1", name: "Chess", chatIds, vector: new Float32Array(0) }] };
}

function titles(plan: ReturnType<typeof planContinuation>): string[] {
  return plan.parts.filter((part) => part.kind === "title").map((part) => part.text);
}

describe("planContinuation", () => {
  // The fixture's reply names chats 5, 3 and 4 of the thread.
  it("names the thread's own chats when the bundle holds them", () => {
    const plan = planContinuation(found, library, chats, bundleOf(c1.id, c3.id, c5.id, found.id));
    expect(plan.source).toBe("thread");
    expect(plan.threadId).toBe("sample-t1");
    expect(plan.question).toBe(thread.continuation.question);
    expect(plan.slots).toBe(3);
    expect(plan.named).toBe(3);
    expect(titles(plan)).toContain(c5.title);
    expect(titles(plan)).toContain(c3.title);
    // Chat 4 is not in the bundle, so the nearest unused thread chat stands in for it.
    expect(titles(plan)).toContain(c1.title);
    expect(plan.text).not.toContain("{{");
    expect(plan.bundleChatIds).toEqual(new Set([c1.id, c3.id, c5.id, found.id]));
  });

  it("never names the found chat itself and leans on other bundle members when the thread is elsewhere", () => {
    const plan = planContinuation(found, library, chats, bundleOf(oneOff.id, found.id));
    expect(plan.source).toBe("thread");
    expect(plan.named).toBe(1);
    expect(titles(plan)).toEqual([oneOff.title]);
    expect(plan.text).not.toContain(found.title);
    expect(plan.text).not.toContain("{{");
  });

  it("drops every slot and tidies the sentence when the chat is loose", () => {
    for (const bundling of [{ bundles: [] }, null]) {
      const plan = planContinuation(found, library, chats, bundling);
      expect(plan.source).toBe("thread");
      expect(plan.slots).toBe(3);
      expect(plan.named).toBe(0);
      expect(plan.text).not.toContain("{{");
      expect(plan.text).toContain("Add fifteen minutes");
      expect(plan.text).not.toMatch(/\s[,.]/);
      expect(plan.bundleChatIds).toEqual(new Set([found.id]));
    }
  });

  it("uses the bundle fallback for a one-off with company, naming the oldest members", () => {
    const plan = planContinuation(oneOff, library, chats, bundleOf(c1.id, c3.id, oneOff.id));
    expect(plan.source).toBe("fallback");
    expect(plan.threadId).toBeNull();
    expect(plan.question).toBe(FALLBACK_CONTINUATION.question);
    expect(plan.slots).toBe(3);
    expect(plan.named).toBe(2);
    expect(titles(plan)).toEqual([c1.title, c3.title]);
    expect(plan.text).not.toContain(oneOff.title);
    expect(plan.text).toContain("which usually means the basics have stuck");
  });

  it("uses the loose fallback for a one-off on its own", () => {
    const plan = planContinuation(oneOff, library, chats, null);
    expect(plan.source).toBe("loose");
    expect(plan.slots).toBe(0);
    expect(plan.named).toBe(0);
    expect(plan.text).toBe(LOOSE_CONTINUATION.reply);
    expect(plan.question).toBe(LOOSE_CONTINUATION.question);
  });
});
