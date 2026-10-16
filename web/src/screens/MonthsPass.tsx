import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Clock } from "../components/Clock";
import { mulberry32, shuffle } from "../content/assemble";
import { getLibrary } from "../content/library";
import type { HistoryChat, LibraryChat, LibraryInterest } from "../content/types";
import { useFlow } from "../state/flow";
import { usePrefersReducedMotion } from "../state/useMediaQuery";
import "./MonthsPass.css";

/**
 * Ids of the chats that arrive while the months pass start with this, so that a
 * revisit of the step finds them again instead of piling in a second batch.
 * Their libraryId stays the plain library id, which the precomputed embeddings use.
 */
export const LATER_PREFIX = "later-";
/** How long the clock runs. */
export const CLOCK_MS = 3000;
/** Pause on the final count before moving on; longer with reduced motion, as nothing animates. */
const HOLD_MS = 900;
const HOLD_REDUCED_MS = 2200;
/** The later chats span this many days after the visitor's last chat: about three months. */
export const LATER_SPAN_DAYS = 92;
export const LATER_MIN = 24;
export const LATER_MAX = 40;

const DAY_MS = 24 * 60 * 60 * 1000;

export interface PickLaterOptions {
  /** The library to draw from. Defaults to the files in src/content/library. */
  library?: LibraryInterest[];
  spanDays?: number;
  min?: number;
  max?: number;
}

interface Pick {
  chat: LibraryChat;
  interest: string;
  threadId: string | null;
  /** Position inside its thread, to keep a thread's chats in order. */
  index: number;
}

/** True for a chat that arrived while the months passed. */
export function isLater(chat: HistoryChat): boolean {
  return chat.id.startsWith(LATER_PREFIX);
}

/**
 * The moment the later chats start after: the visitor's newest own chat, else the
 * newest chat in the history that is not itself a later one. Null when there are no chats.
 */
export function anchorDate(history: HistoryChat[], myChats: HistoryChat[]): Date | null {
  const own = myChats.map((chat) => Date.parse(chat.date)).filter(Number.isFinite);
  const base = (
    own.length > 0 ? own : history.filter((c) => !isLater(c)).map((c) => Date.parse(c.date))
  ).filter(Number.isFinite);
  if (base.length === 0) return null;
  return new Date(Math.max(...base));
}

/** Keeps each thread's chats in their original order while leaving everything else where the shuffle put it. */
function restoreThreadOrder(picks: Pick[]): Pick[] {
  const out = picks.slice();
  const byThread = new Map<string, number[]>();
  out.forEach((pick, position) => {
    if (pick.threadId === null) return;
    const positions = byThread.get(pick.threadId) ?? [];
    positions.push(position);
    byThread.set(pick.threadId, positions);
  });
  for (const positions of byThread.values()) {
    const ordered = positions
      .map((position) => out[position] as Pick)
      .sort((a, b) => a.index - b.index);
    positions.forEach((position, i) => {
      out[position] = ordered[i] as Pick;
    });
  }
  return out;
}

/**
 * The chats that arrive after the visitor's own: 24 to 40 library chats not yet in
 * the history, preferring the chosen interests, dated after `after` and spread over
 * about three months with a thread's chats kept in order. Deterministic for a seed.
 */
export function pickLater(
  interests: string[],
  history: HistoryChat[],
  myChats: HistoryChat[],
  seed: number,
  after: Date,
  options: PickLaterOptions = {},
): HistoryChat[] {
  const library = options.library ?? getLibrary();
  const span = options.spanDays ?? LATER_SPAN_DAYS;
  const min = options.min ?? LATER_MIN;
  const max = options.max ?? LATER_MAX;
  // A different stream from the history's, so the two never share a sequence.
  const random = mulberry32((seed ^ 0x6d6f6e74) | 0);

  const used = new Set([...history, ...myChats].map((chat) => chat.libraryId));
  const chosen = new Set(interests);
  const fromChosen: Pick[] = [];
  const fromOthers: Pick[] = [];
  for (const entry of library) {
    const target = chosen.has(entry.interest) ? fromChosen : fromOthers;
    entry.oneOffs.forEach((chat, index) => {
      if (!used.has(chat.id))
        target.push({ chat, interest: entry.interest, threadId: null, index });
    });
    for (const thread of entry.threads) {
      thread.chats.forEach((chat, index) => {
        if (!used.has(chat.id)) {
          target.push({ chat, interest: entry.interest, threadId: thread.id, index });
        }
      });
    }
  }

  const want = min + Math.floor(random() * (max - min + 1));
  const pool = [...shuffle(fromChosen, random), ...shuffle(fromOthers, random)];
  const picks = restoreThreadOrder(pool.slice(0, Math.min(want, pool.length)));

  // Days after the anchor, at a time between about 07:00 and 22:00, in rising order.
  const days = picks
    .map(() => Math.floor(1 + random() * (span - 1)) + (7 + random() * 15) / 24)
    .sort((a, b) => a - b);

  const start = after.getTime();
  return picks.map(({ chat, interest, threadId }, i) => ({
    id: `${LATER_PREFIX}${chat.id}`,
    libraryId: chat.id,
    title: chat.title,
    question: chat.question,
    reply: chat.reply,
    paraphrase: chat.paraphrase,
    interest,
    threadId,
    date: new Date(start + (days[i] ?? 1) * DAY_MS).toISOString(),
    mine: false,
  }));
}

/** "October", in British English. */
export function monthLabel(date: Date): string {
  return date.toLocaleDateString("en-GB", { month: "long" });
}

/** "14 Nov", in British English. */
export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** Slow start, quick middle, soft landing. */
export function easeInOut(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2;
}

/** The "months" step: a clock turns for about three seconds while more chats pile in. */
export function MonthsPass() {
  const { state, dispatch } = useFlow();
  const reduce = usePrefersReducedMotion();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const finishedRef = useRef(false);
  const [progress, setProgress] = useState(reduce ? 1 : 0);
  // The demo's fixed "today" (else the real clock) is only a fallback anchor for a history with no chats.
  const [fallbackNow] = useState(() => (state.now ? new Date(state.now) : new Date()));

  const { history, myChats, personality, seed } = state;
  const existing = useMemo(() => history.filter(isLater), [history]);
  const after = useMemo(
    () => anchorDate(history, myChats) ?? fallbackNow,
    [history, myChats, fallbackNow],
  );
  const pile = useMemo(
    () =>
      existing.length > 0
        ? existing
        : pickLater(personality?.interests ?? [], history, myChats, seed, after),
    [existing, personality, history, myChats, seed, after],
  );
  const end = useMemo(() => new Date(after.getTime() + LATER_SPAN_DAYS * DAY_MS), [after]);

  const finish = useCallback(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    if (existing.length === 0 && pile.length > 0) dispatch({ type: "appendHistory", chats: pile });
    dispatch({ type: "go", step: "challenge" });
  }, [dispatch, existing.length, pile]);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  // Drive the clock from the frame clock, so a hidden tab simply catches up.
  useEffect(() => {
    if (reduce) {
      setProgress(1);
      return;
    }
    const started = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - started) / CLOCK_MS);
      setProgress(p);
      if (p < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [reduce]);

  // Hold on the final count, then carry on by itself.
  useEffect(() => {
    if (progress < 1) return;
    const timer = window.setTimeout(finish, reduce ? HOLD_REDUCED_MS : HOLD_MS);
    return () => window.clearTimeout(timer);
  }, [progress, finish, reduce]);

  const eased = easeInOut(progress);
  const shown = Math.round(eased * pile.length);
  const visible = pile.slice(0, shown).reverse();
  const current = new Date(after.getTime() + eased * LATER_SPAN_DAYS * DAY_MS);
  const done = progress >= 1;
  const counter = pile.length > 0 ? `+${shown} chats later…` : "The months roll by…";
  const summary =
    pile.length > 0
      ? `${pile.length} more chats arrived between ${monthLabel(after)} and ${monthLabel(end)}.`
      : `The months passed, from ${monthLabel(after)} to ${monthLabel(end)}.`;

  return (
    <section className="screen months" data-step="months" aria-labelledby="months-title">
      <div className="months__story">
        <p className="screen__kicker">Step 5 of 8 · months pass</p>
        <h1 id="months-title" ref={headingRef} tabIndex={-1}>
          Time flies.
        </h1>
        <p className="screen__lede">You get on with life. The chats keep coming.</p>
        <Clock
          className="months__clock"
          progress={eased}
          label={monthLabel(current)}
          description={`A clock turning from ${monthLabel(after)} to ${monthLabel(end)}`}
        />
        <p className="months__counter" aria-hidden="true">
          {counter}
        </p>
        <p className="visually-hidden" aria-live="polite">
          {done ? summary : ""}
        </p>
        <div className="screen__actions">
          <Button variant="secondary" onClick={finish}>
            Skip
          </Button>
        </div>
      </div>
      <div className="months__pile card">
        <p className="months__pile-title">Your chats</p>
        <ul className="pile">
          {visible.map((chat) => (
            <li key={chat.id} className="pile__item">
              <span className="pile__title">{chat.title}</span>
              <time className="pile__date" dateTime={chat.date}>
                {dayLabel(chat.date)}
              </time>
            </li>
          ))}
        </ul>
        {visible.length === 0 ? (
          <p className="pile__empty">{done ? "Nothing new arrived." : "Any moment now…"}</p>
        ) : null}
      </div>
    </section>
  );
}
