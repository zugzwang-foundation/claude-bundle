import { getLibrary } from "./library";
import type { HistoryChat, LibraryChat, LibraryInterest } from "./types";

/** The history holds between these many chats. */
export const HISTORY_MIN = 100;
export const HISTORY_MAX = 150;
/** Nine months, in days. */
export const HISTORY_SPAN_DAYS = 274;

const DAY_MS = 24 * 60 * 60 * 1000;

/** mulberry32: a small, fast, seedable generator returning numbers in [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher-Yates shuffle with the given generator; returns a new array. */
export function shuffle<T>(items: readonly T[], random: () => number): T[] {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    const a = out[i] as T;
    out[i] = out[j] as T;
    out[j] = a;
  }
  return out;
}

export interface AssembleOptions {
  /** The fixed "today": the newest chat is dated shortly before it. */
  now: Date;
  /** The library to draw from. Defaults to the files in src/content/library. */
  library?: LibraryInterest[];
  spanDays?: number;
  min?: number;
  max?: number;
}

interface Draft {
  chat: LibraryChat;
  interest: string;
  threadId: string | null;
  /** Days since the start of the span, fractional. */
  t: number;
}

/**
 * Increasing times for one thread's chats: a window inside the span,
 * with at least two days between chats (so flooring to a day keeps a full day's gap).
 */
function threadTimes(count: number, span: number, random: () => number): number[] {
  const start = random() * span * 0.45;
  const length = span * (0.35 + random() * 0.5);
  const end = Math.min(span - 1, start + length);
  const points = Array.from({ length: count }, () => start + random() * (end - start)).sort(
    (a, b) => a - b,
  );
  const minGap = 2;
  for (let i = 1; i < points.length; i += 1) {
    const previous = points[i - 1] as number;
    const current = points[i] as number;
    if (current < previous + minGap) points[i] = previous + minGap;
  }
  const last = points[points.length - 1] ?? start;
  if (last > span - 1 && last > start) {
    const scale = (span - 1 - start) / (last - start);
    return points.map((p) => start + (p - start) * scale);
  }
  return points;
}

function draft(
  chat: LibraryChat,
  interest: string,
  threadId: string | null,
  t: number,
  random: () => number,
): Draft {
  // On that day, at a time between about 07:00 and 22:00.
  const hour = (7 + random() * 15) / 24;
  return { chat, interest, threadId, t: Math.floor(t) + hour };
}

/**
 * Build a visitor's history: every thread and one-off of the chosen interests,
 * padded with one-offs from other interests up to `min`, capped at `max`, and
 * spread over nine months ending at `now`. Thread order is preserved.
 * Deterministic for a given seed.
 */
export function assemble(
  interests: string[],
  seed: number,
  options: AssembleOptions,
): HistoryChat[] {
  const library = options.library ?? getLibrary();
  const span = options.spanDays ?? HISTORY_SPAN_DAYS;
  const min = options.min ?? HISTORY_MIN;
  const max = options.max ?? HISTORY_MAX;
  const random = mulberry32(seed);

  const chosen = interests
    .map((id) => library.find((entry) => entry.interest === id))
    .filter((entry): entry is LibraryInterest => entry !== undefined);
  const chosenIds = new Set(chosen.map((entry) => entry.interest));
  const others = library.filter((entry) => !chosenIds.has(entry.interest));

  const drafts: Draft[] = [];
  for (const entry of chosen) {
    for (const thread of entry.threads) {
      const times = threadTimes(thread.chats.length, span, random);
      thread.chats.forEach((chat, index) => {
        drafts.push(draft(chat, entry.interest, thread.id, times[index] ?? 0, random));
      });
    }
    for (const chat of entry.oneOffs) {
      drafts.push(draft(chat, entry.interest, null, random() * (span - 1), random));
    }
  }

  const pool = shuffle(
    others.flatMap((entry) => entry.oneOffs.map((chat) => ({ chat, interest: entry.interest }))),
    random,
  );
  while (drafts.length < min && pool.length > 0) {
    const next = pool.pop();
    if (!next) break;
    drafts.push(draft(next.chat, next.interest, null, random() * (span - 1), random));
  }

  // Over the cap: drop one-offs from the end (padding first), never thread chats.
  for (let i = drafts.length - 1; i >= 0 && drafts.length > max; i -= 1) {
    if (drafts[i]?.threadId === null) drafts.splice(i, 1);
  }
  if (drafts.length > max) drafts.length = max;

  const start = options.now.getTime() - span * DAY_MS;
  return drafts
    .sort((a, b) => a.t - b.t)
    .map(({ chat, interest, threadId, t }) => ({
      id: chat.id,
      libraryId: chat.id,
      title: chat.title,
      question: chat.question,
      reply: chat.reply,
      paraphrase: chat.paraphrase,
      interest,
      threadId,
      date: new Date(start + Math.min(t, span - 1 / 24) * DAY_MS).toISOString(),
      mine: false,
    }));
}

/** Chats dated on or before `date`, then those after it: the history and the pile that arrives later. */
export function splitByDate(chats: HistoryChat[], date: Date): [HistoryChat[], HistoryChat[]] {
  const cut = date.getTime();
  const before: HistoryChat[] = [];
  const after: HistoryChat[] = [];
  for (const chat of chats) {
    (Date.parse(chat.date) <= cut ? before : after).push(chat);
  }
  return [before, after];
}
