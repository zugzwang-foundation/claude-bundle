import type { BundlingResult } from "../sorter/bundler";
import type { HistoryChat, LibraryInterest, LibraryThread } from "./types";

/**
 * A thread's continuation reply carries slots like {{chat:3}}: "the third chat
 * of this thread". The demo fills each slot with the title of a chat that is
 * actually in the found chat's bundle, so the reply only ever leans on context
 * the sorter really gathered. This module does that filling, with no React.
 */

/** Matches one slot. The group is whatever follows "chat:", usually a 1-based position. */
export const SLOT_PATTERN = /\{\{\s*chat:\s*([^}]*?)\s*\}\}/g;

/** One piece of a filled reply: plain text, or a title that filled a slot. */
export type ContinuationPart =
  | { kind: "text"; text: string }
  | { kind: "title"; text: string; chatId: string };

export interface Continuation {
  question: string;
  reply: string;
  /** The thread's chats in thread order, as they appear in the visitor's history. */
  threadChats: HistoryChat[];
  threadId: string;
  topic: string;
}

/** Private-use characters that mark a dropped slot and the edges of a filled title while tidying. */
const DROPPED = "\uE000";
/** A dropped slot whose leading word ("from", "in", "the") was removed with it. */
const DROPPED_AFTER_WORD = "\uE003";
const TITLE_OPEN = "\uE001";
const TITLE_CLOSE = "\uE002";
const ANY_DROPPED = `[${DROPPED}${DROPPED_AFTER_WORD}]`;

/** Words that only make sense when something follows them, e.g. "from {{chat:5}}". */
const LEADING_WORDS =
  "from|in|as|of|at|with|about|on|to|for|like|using|via|through|see|recall|the|a|an";

interface Slot {
  /** Index into the parts being built. */
  index: number;
  /** The 1-based position asked for, or null when unreadable. */
  position: number | null;
  chat: HistoryChat | null;
}

function isInBundle(chat: HistoryChat, bundleChatIds: ReadonlySet<string>): boolean {
  return bundleChatIds.has(chat.id);
}

/**
 * Resolve every slot to a chat or to null. Direct hits win first, so that a
 * substitute never steals a chat another slot names outright. Substitutes are
 * the nearest unused in-bundle chat of the same thread, earlier on a tie.
 */
function resolveSlots(
  slots: Slot[],
  threadChats: readonly HistoryChat[],
  bundleChatIds: ReadonlySet<string>,
): void {
  const used = new Set<string>();
  for (const slot of slots) {
    const direct = slot.position === null ? undefined : threadChats[slot.position - 1];
    if (direct && isInBundle(direct, bundleChatIds) && !used.has(direct.id)) {
      slot.chat = direct;
      used.add(direct.id);
    }
  }
  for (const slot of slots) {
    if (slot.chat) continue;
    const wanted = slot.position ?? 1;
    let best: HistoryChat | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let index = 0; index < threadChats.length; index += 1) {
      const chat = threadChats[index];
      if (!chat || !isInBundle(chat, bundleChatIds) || used.has(chat.id)) continue;
      const distance = Math.abs(index + 1 - wanted);
      if (distance < bestDistance) {
        best = chat;
        bestDistance = distance;
      }
    }
    if (best) {
      slot.chat = best;
      used.add(best.id);
    }
  }
}

function replaceUntilStable(text: string, pattern: RegExp, replacement: string): string {
  let out = text;
  for (let i = 0; i < 8; i += 1) {
    const next = out.replace(pattern, replacement);
    if (next === out) break;
    out = next;
  }
  return out;
}

/**
 * Tidy a reply after slots were dropped. Each marker stands where a slot used
 * to be; every rule is anchored on a marker, so text away from a dropped slot
 * is left exactly as written. Two flavours of marker: a slot dropped on its
 * own, and one whose leading word ("from", "the") went with it. After a
 * removed word the conjunction stays ("the picks and the trick from X");
 * after a bare drop it goes ("Keep X close", not "Keep and X close").
 */
export function tidyDropped(text: string): string {
  if (!text.includes(DROPPED)) return text;
  let out = text;
  // "the blunder check from ▮" -> "the blunder check ▮"; repeats for "as in the ▮".
  out = replaceUntilStable(
    out,
    new RegExp(`\\b(?:${LEADING_WORDS})\\s+${ANY_DROPPED}`, "gi"),
    DROPPED_AFTER_WORD,
  );
  // "▮ and ▮", "▮, ▮" -> one marker; the word-flavoured one wins so its conjunction survives.
  out = replaceUntilStable(
    out,
    new RegExp(`${DROPPED}\\s*,?\\s*(?:\\b(?:and|or)\\s+)?${DROPPED_AFTER_WORD}`, "gi"),
    DROPPED_AFTER_WORD,
  );
  out = replaceUntilStable(
    out,
    new RegExp(`${DROPPED_AFTER_WORD}\\s*,?\\s*(?:\\b(?:and|or)\\s+)?${ANY_DROPPED}`, "gi"),
    DROPPED_AFTER_WORD,
  );
  out = replaceUntilStable(
    out,
    new RegExp(`${DROPPED}\\s*,?\\s*(?:\\b(?:and|or)\\s+)?${DROPPED}`, "gi"),
    DROPPED,
  );
  // "X, Y, and ▮." -> "X, Y▮." (a dangling conjunction before the end of a clause).
  out = out.replace(
    new RegExp(`,?\\s*\\b(?:and|or)\\s+(${ANY_DROPPED})(?=\\s*(?:[,.;:!?]|$))`, "gi"),
    "$1",
  );
  // "▮ and Y both matter" at the start of a clause -> "▮Y both matter".
  out = out.replace(
    new RegExp(`(^|[.!?:]\\s*)${ANY_DROPPED}\\s*,?\\s*\\b(?:and|or)\\s+`, "gi"),
    `$1${DROPPED}`,
  );
  // "Keep ▮ and Y close" -> "Keep ▮Y close" (a bare drop takes its conjunction with it).
  out = out.replace(new RegExp(`${DROPPED}\\s*,?\\s*\\b(?:and|or)\\s+`, "gi"), DROPPED);
  // "(▮)" -> "".
  out = out.replace(new RegExp(`\\(\\s*${ANY_DROPPED}\\s*\\)`, "g"), DROPPED);
  out = out.replace(new RegExp(ANY_DROPPED, "g"), "");
  // Punctuation left behind: " ,", ", ,", ", .", double spaces, a leading comma.
  out = out.replace(/\s+([,.;:!?])/g, "$1");
  out = out.replace(/(?:,\s*){2,}/g, ", ");
  out = out.replace(/,(?=[.;:!?])/g, "");
  out = out.replace(/:(?=[.;!?])/g, "");
  out = out.replace(/[ \t]{2,}/g, " ");
  out = out.replace(/^[\s,.;:]+/, "");
  out = out.trim();
  // A clause that now starts with a lowercase word.
  out = out.replace(
    /(^|[.!?]\s+)([a-z])/g,
    (_match, before: string, letter: string) => `${before}${letter.toUpperCase()}`,
  );
  return out;
}

/**
 * Fill a continuation reply and keep the seams: each part is either text or
 * the title that filled a slot. Joining the parts gives `fillContinuation`.
 */
export function fillContinuationParts(
  reply: string,
  threadChats: readonly HistoryChat[],
  bundleChatIds: ReadonlySet<string>,
): ContinuationPart[] {
  const slots: Slot[] = [];
  const pieces: string[] = [];
  let last = 0;
  SLOT_PATTERN.lastIndex = 0;
  for (const match of reply.matchAll(SLOT_PATTERN)) {
    const start = match.index ?? 0;
    pieces.push(reply.slice(last, start));
    const raw = (match[1] ?? "").trim();
    const parsed = /^\d+$/.test(raw) ? Number.parseInt(raw, 10) : Number.NaN;
    slots.push({
      index: pieces.length,
      position: Number.isInteger(parsed) && parsed >= 1 ? parsed : null,
      chat: null,
    });
    pieces.push("");
    last = start + match[0].length;
  }
  pieces.push(reply.slice(last));
  if (slots.length === 0) return reply.length > 0 ? [{ kind: "text", text: reply }] : [];

  resolveSlots(slots, threadChats, bundleChatIds);

  const filled: HistoryChat[] = [];
  for (const slot of slots) {
    if (slot.chat) {
      pieces[slot.index] = `${TITLE_OPEN}${filled.length}${TITLE_CLOSE}`;
      filled.push(slot.chat);
    } else {
      pieces[slot.index] = DROPPED;
    }
  }

  const tidied = tidyDropped(pieces.join(""));
  const parts: ContinuationPart[] = [];
  const token = new RegExp(`${TITLE_OPEN}(\\d+)${TITLE_CLOSE}`, "g");
  let cursor = 0;
  for (const match of tidied.matchAll(token)) {
    const start = match.index ?? 0;
    const text = tidied.slice(cursor, start);
    if (text) parts.push({ kind: "text", text });
    const chat = filled[Number.parseInt(match[1] ?? "0", 10)];
    if (chat) parts.push({ kind: "title", text: chat.title, chatId: chat.id });
    cursor = start + match[0].length;
  }
  const tail = tidied.slice(cursor);
  if (tail) parts.push({ kind: "text", text: tail });
  return parts;
}

/**
 * Replace each {{chat:N}} with the title of the thread's N-th chat when that
 * chat is in the bundle; otherwise with the title of another in-bundle chat of
 * the same thread not already used; otherwise drop the slot and tidy the sentence.
 */
export function fillContinuation(
  reply: string,
  threadChats: readonly HistoryChat[],
  bundleChatIds: ReadonlySet<string>,
): string {
  return fillContinuationParts(reply, threadChats, bundleChatIds)
    .map((part) => part.text)
    .join("");
}

function findThread(
  target: HistoryChat,
  library: readonly LibraryInterest[],
): { entry: LibraryInterest; thread: LibraryThread } | null {
  const ordered = [
    ...library.filter((entry) => entry.interest === target.interest),
    ...library.filter((entry) => entry.interest !== target.interest),
  ];
  if (target.threadId !== null) {
    for (const entry of ordered) {
      const thread = entry.threads.find((candidate) => candidate.id === target.threadId);
      if (thread) return { entry, thread };
    }
  }
  for (const entry of ordered) {
    const thread = entry.threads.find((candidate) =>
      candidate.chats.some((chat) => chat.id === target.libraryId),
    );
    if (thread) return { entry, thread };
  }
  return null;
}

/**
 * The continuation for the found chat: its thread's follow-up question and
 * reply, plus the thread's chats as they appear in the history (the visitor's
 * own copy of a chat wins over the library copy). Chats the history lacks are
 * stood in for by the library chat, dated like the target, so positions hold.
 * Null when the target is a one-off or its thread is not in the library.
 */
export function pickContinuation(
  target: HistoryChat,
  library: readonly LibraryInterest[],
  history: readonly HistoryChat[] = [],
): Continuation | null {
  const found = findThread(target, library);
  if (!found) return null;
  const { entry, thread } = found;
  const threadChats = thread.chats.map((libraryChat): HistoryChat => {
    const copies = history.filter((chat) => chat.libraryId === libraryChat.id);
    const chosen =
      copies.find((chat) => chat.id === target.id) ?? copies.find((chat) => chat.mine) ?? copies[0];
    if (chosen) return chosen;
    if (target.libraryId === libraryChat.id) return target;
    return {
      id: libraryChat.id,
      libraryId: libraryChat.id,
      title: libraryChat.title,
      question: libraryChat.question,
      reply: libraryChat.reply,
      paraphrase: libraryChat.paraphrase,
      interest: entry.interest,
      threadId: thread.id,
      date: target.date,
      mine: false,
    };
  });
  return {
    question: thread.continuation.question,
    reply: thread.continuation.reply,
    threadChats,
    threadId: thread.id,
    topic: thread.topic,
  };
}

/**
 * The ids of every chat in the bundle that holds `chatId`. A loose chat, or no
 * bundling yet, gives a set with just that chat, so its own slot can still fill.
 */
export function bundleChatIdsFor(
  chatId: string,
  bundling: Pick<BundlingResult, "bundles"> | null | undefined,
): Set<string> {
  const bundle = bundling?.bundles.find((candidate) => candidate.chatIds.includes(chatId));
  return new Set(bundle ? bundle.chatIds : [chatId]);
}
