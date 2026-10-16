import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { HistoryChat } from "../content/types";
import { ContinuationReply } from "./ContinuationReply";

const chat = (id: string, title: string): HistoryChat => ({
  id,
  libraryId: id,
  title,
  question: "q",
  reply: "r",
  paraphrase: "p",
  interest: "sample",
  threadId: "t",
  date: "2026-03-01T09:00:00.000Z",
  mine: false,
});

const chats = [
  chat("c1", "Chess basics"),
  chat("c2", "Castling early"),
  chat("c3", "Rook endgames"),
];

describe("ContinuationReply", () => {
  it("renders filled titles as marks and the rest as plain text", () => {
    const html = renderToStaticMarkup(
      createElement(ContinuationReply, {
        reply: "Keep {{chat:2}} going and revisit {{chat:3}}.",
        threadChats: chats,
        bundleChatIds: new Set(["c2", "c3"]),
        "aria-live": "polite",
        id: "reply",
      }),
    );
    expect(html).toContain('<p class="continuation-reply" aria-live="polite" id="reply">');
    expect(html).toContain(
      '<mark class="continuation-reply__title" data-chat-id="c2" style="--i:0">Castling early</mark>',
    );
    expect(html).toContain(
      '<mark class="continuation-reply__title" data-chat-id="c3" style="--i:1">Rook endgames</mark>',
    );
    expect(html.replace(/<[^>]+>/g, "")).toBe(
      "Keep Castling early going and revisit Rook endgames.",
    );
  });

  it("shows no mark for a dropped slot", () => {
    const html = renderToStaticMarkup(
      createElement(ContinuationReply, {
        reply: "Revisit {{chat:3}} soon.",
        threadChats: chats,
        bundleChatIds: new Set<string>(),
        className: "extra",
      }),
    );
    expect(html).not.toContain("<mark");
    expect(html).toContain('class="continuation-reply extra"');
    expect(html.replace(/<[^>]+>/g, "")).toBe("Revisit soon.");
  });
});
