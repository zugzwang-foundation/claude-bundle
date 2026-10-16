import { describe, expect, it } from "vitest";
import type { HistoryChat } from "../content/types";
import { bundleChats } from "./bundler";
import calibration from "./calibration.json";
import { l2Normalize } from "./scoring";
import { chatText } from "./text";

function chat(id: string, title: string, day: number, mine = false): HistoryChat {
  return {
    id,
    libraryId: id,
    title,
    question: `${title}?`,
    reply: "reply",
    paraphrase: "para",
    interest: "x",
    threadId: null,
    date: new Date(Date.UTC(2026, 0, 1 + day)).toISOString(),
    mine,
  };
}

/** A fake embedder: the same first word gives the same direction. */
const directions: Record<string, number[]> = {
  chess: [1, 0, 0, 0],
  bread: [0, 1, 0, 0],
  taxes: [0, 0, 1, 0],
};
async function embed(texts: string[]): Promise<Float32Array[]> {
  return texts.map((text) => {
    const word = text.split(/\s+/)[0]?.toLowerCase() ?? "";
    const base = directions[word] ?? [0, 0, 0, 1];
    return l2Normalize(base);
  });
}

describe("bundleChats", () => {
  it("files near-identical chats together, names the bundle after the older chat and leaves strangers loose", async () => {
    const chats = [
      chat("c3", "Taxes for freelancers", 3),
      chat("c1", "Chess openings", 1),
      chat("c2", "Chess endgames", 2),
      chat("c4", "Chess tactics", 4, true),
    ];
    const result = await bundleChats(chats, { calibration, embed, now: () => 0 });
    expect(result.bundles).toHaveLength(1);
    const bundle = result.bundles[0];
    expect(bundle?.name).toBe("Chess openings");
    expect(bundle?.chatIds).toEqual(["c1", "c2", "c4"]);
    expect(result.loose).toEqual(["c3"]);
    expect(result.placements.c1?.bundleId).toBe(bundle?.id);
    expect(result.placements.c2).toMatchObject({ action: "file", bundleId: bundle?.id });
    expect(result.placements.c3).toMatchObject({ action: "leave", bundleId: null });
    expect(result.steps.map((s) => s.chatId)).toEqual(["c1", "c2", "c3", "c4"]);
    expect(result.steps[1]?.createdBundleId).toBe(bundle?.id);
  });

  it("uses precomputed vectors for library chats but embeds the visitor's own live", async () => {
    const seen: string[] = [];
    const spyEmbed = async (texts: string[]) => {
      seen.push(...texts);
      return embed(texts);
    };
    const chats = [chat("a", "Bread starter", 1), chat("b", "Bread shaping", 2, true)];
    const precomputed = { a: l2Normalize([0, 1, 0, 0]), b: l2Normalize([0, 0, 0, 1]) };
    const result = await bundleChats(chats, {
      calibration,
      embed: spyEmbed,
      precomputed,
      now: () => 0,
    });
    expect(seen).toEqual([chatText(chats[1] as HistoryChat)]);
    expect(result.bundles).toHaveLength(1);
  });

  it("reports probabilities, timings and empty input", async () => {
    const result = await bundleChats([], { calibration, embed, now: () => 0 });
    expect(result).toMatchObject({ bundles: [], loose: [], steps: [], decisionMs: 0 });
    const one = await bundleChats([chat("solo", "Chess", 1)], { calibration, embed });
    expect(one.loose).toEqual(["solo"]);
    expect(one.steps[0]?.probabilities).toEqual({ none: 1 });
  });
});
