import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import type { HistoryChat } from "../content/types";
import { useFlow } from "../state/flow";
import { TEST_MODE } from "../testing";
import { dayLabel, isLater } from "./MonthsPass";
import "./Challenge.css";

/** "Give up" appears after this long; giving up records at least this much time. */
export const GIVE_UP_AFTER_MS = 60_000;

/** Words that carry no topic, ignored when judging how much a paraphrase gives away. */
const STOPWORDS = new Set(
  (
    "a an the and or but of to for in on at by with from into over after before than then " +
    "my your our his her their i me we you it its is was were be been being am are do does did " +
    "how what when where which who whom why that this these those as about so if not no up out " +
    "one ones time chat asked ask whether there just like really get got some any all can could " +
    "should would will had has have while without around"
  ).split(" "),
);

/** Lower case, accents folded, apostrophes dropped. */
export function normalise(text: string): string {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/['’]/g, "");
}

/** The words of a text: letters and digits only. */
export function words(text: string): string[] {
  return normalise(text)
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

/**
 * Ordinary sidebar search: every word typed must appear inside one of the title's
 * words, case-insensitive. "cast" finds "Castling early"; an empty query finds everything.
 */
export function titleMatches(title: string, query: string): boolean {
  const needles = words(query);
  if (needles.length === 0) return true;
  const hay = words(title);
  return needles.every((needle) => hay.some((word) => word.includes(needle)));
}

/** A crude two-stage stem (plural, then ending): enough to see that "openings" and "opening" share a topic. */
export function stem(word: string): string {
  let w = word;
  if (w.length > 5 && w.endsWith("ies")) w = `${w.slice(0, -3)}y`;
  else if (w.length > 3 && w.endsWith("s") && !w.endsWith("ss")) w = w.slice(0, -1);
  for (const suffix of ["ing", "ed", "er"]) {
    if (w.length > suffix.length + 3 && w.endsWith(suffix)) {
      w = w.slice(0, -suffix.length);
      break;
    }
  }
  return w;
}

function contentStems(text: string): string[] {
  return words(text)
    .filter((word) => word.length > 2 && !STOPWORDS.has(word))
    .map(stem);
}

/** How many topic words the paraphrase shares with the title: lower is harder to find. */
export function titleOverlap(title: string, paraphrase: string): number {
  const titleStems = new Set(contentStems(title));
  return contentStems(paraphrase).filter((s) => titleStems.has(s)).length;
}

/**
 * The chat to find: among the visitor's own chats, the one whose paraphrase gives
 * away the fewest title words; ties go to the older chat. Falls back to the history
 * when the visitor asked nothing.
 */
export function pickTarget(myChats: HistoryChat[], history: HistoryChat[]): HistoryChat | null {
  const candidates = myChats.length > 0 ? myChats : history.filter((chat) => !isLater(chat));
  if (candidates.length === 0) return null;
  const sorted = candidates
    .slice()
    .sort(
      (a, b) =>
        titleOverlap(a.title, a.paraphrase) - titleOverlap(b.title, b.paraphrase) ||
        Date.parse(a.date) - Date.parse(b.date) ||
        a.id.localeCompare(b.id),
    );
  return sorted[0] ?? null;
}

/** "0:07", "1:02". */
export function formatSeconds(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export interface MonthGroup {
  key: string;
  label: string;
  chats: HistoryChat[];
}

/** Newest first, grouped by month, as a sidebar would show them. */
export function groupByMonth(chats: HistoryChat[]): MonthGroup[] {
  const groups: MonthGroup[] = [];
  for (const chat of chats) {
    const date = new Date(chat.date);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    const last = groups[groups.length - 1];
    if (last && last.key === key) {
      last.chats.push(chat);
    } else {
      groups.push({
        key,
        label: date.toLocaleDateString("en-GB", { month: "long", year: "numeric" }),
        chats: [chat],
      });
    }
  }
  return groups;
}

function newestFirst(a: HistoryChat, b: HistoryChat): number {
  return Date.parse(b.date) - Date.parse(a.date) || a.id.localeCompare(b.id);
}

/** The "challenge" step: find one chat by hand, against a visible clock. */
export function Challenge() {
  const { state, dispatch } = useFlow();
  const { history, myChats, challenge } = state;
  const headingRef = useRef<HTMLHeadingElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const startRef = useRef(0);
  const doneRef = useRef(false);
  const [elapsed, setElapsed] = useState(0);
  const [query, setQuery] = useState("");
  const [wrongTaps, setWrongTaps] = useState(0);
  const [shakeId, setShakeId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [countText, setCountText] = useState("");

  const chats = useMemo(() => [...history, ...myChats].sort(newestFirst), [history, myChats]);
  const target = useMemo(() => {
    const kept = challenge.targetId ? chats.find((c) => c.id === challenge.targetId) : undefined;
    return kept ?? pickTarget(myChats, history);
  }, [challenge.targetId, chats, myChats, history]);

  useEffect(() => {
    if (target && challenge.targetId !== target.id) {
      dispatch({ type: "setChallengeTarget", targetId: target.id });
    }
  }, [target, challenge.targetId, dispatch]);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  // The clock starts when the screen appears and ticks four times a second.
  useEffect(() => {
    startRef.current = performance.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed(performance.now() - startRef.current), 250);
    return () => window.clearInterval(timer);
  }, []);

  const matches = useMemo(
    () => (words(query).length === 0 ? chats : chats.filter((c) => titleMatches(c.title, query))),
    [chats, query],
  );
  const groups = useMemo(() => groupByMonth(matches), [matches]);
  const searching = words(query).length > 0;

  // Announce the number of matches a moment after typing stops, not on every key.
  useEffect(() => {
    const text = searching
      ? `${matches.length} of ${chats.length} chats match`
      : `${chats.length} chats`;
    const timer = window.setTimeout(() => setCountText(text), 400);
    return () => window.clearTimeout(timer);
  }, [matches.length, chats.length, searching]);

  const canGiveUp = elapsed >= GIVE_UP_AFTER_MS;
  useEffect(() => {
    if (canGiveUp) setStatus("Still looking? You can give up now.");
  }, [canGiveUp]);

  function leave(ms: number, gaveUp: boolean) {
    if (doneRef.current) return;
    doneRef.current = true;
    dispatch({ type: "setChallengeTime", which: "before", ms });
    dispatch({ type: "setChallengeGaveUp", gaveUp });
    dispatch({ type: "go", step: "reveal" });
  }

  function tap(chat: HistoryChat) {
    if (!target || doneRef.current) return;
    const correct = chat.id === target.id || chat.libraryId === target.libraryId;
    if (correct) {
      leave(Math.round(performance.now() - startRef.current), false);
      return;
    }
    setWrongTaps((n) => n + 1);
    setShakeId(chat.id);
    setStatus(
      wrongTaps === 0
        ? "Not that one. Keep looking."
        : `Not that one either. ${wrongTaps + 1} tries so far.`,
    );
  }

  function giveUp() {
    leave(Math.max(GIVE_UP_AFTER_MS, Math.round(performance.now() - startRef.current)), true);
  }

  function onSearchKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && matches.length === 1 && matches[0]) {
      event.preventDefault();
      tap(matches[0]);
    }
  }

  if (!target) {
    return (
      <section className="screen challenge" data-step="challenge" aria-labelledby="challenge-title">
        <p className="screen__kicker">Step 6 of 8 · the challenge</p>
        <h1 id="challenge-title" ref={headingRef} tabIndex={-1}>
          Nothing to find yet
        </h1>
        <p className="screen__lede">
          There are no chats in this history, so there is nothing to lose. Carry on to see the
          sorter anyway.
        </p>
        <div className="screen__actions">
          <Button size="lg" onClick={() => dispatch({ type: "next" })}>
            Next
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="screen challenge" data-step="challenge" aria-labelledby="challenge-title">
      <div className="challenge__brief">
        <p className="screen__kicker">Step 6 of 8 · the challenge</p>
        <h1
          id="challenge-title"
          ref={headingRef}
          tabIndex={-1}
          data-target-title={TEST_MODE ? target.title : undefined}
        >
          Find that chat
        </h1>
        <p className="screen__lede">
          Months later, you need it again. Find the chat where you asked about{" "}
          <q className="challenge__paraphrase" data-testid="challenge-paraphrase">
            {target.paraphrase}
          </q>
        </p>
        <div className="challenge__toolbar">
          <div className="challenge__search">
            <label className="challenge__label" htmlFor="challenge-search">
              Search your chats
            </label>
            <input
              id="challenge-search"
              ref={searchRef}
              className="challenge__input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={onSearchKey}
              placeholder="Words from the title…"
              autoComplete="off"
              spellCheck={false}
              aria-describedby="challenge-search-hint"
            />
            <p id="challenge-search-hint" className="challenge__hint">
              Titles only, like any chat sidebar.
            </p>
          </div>
          <p className="challenge__timer" role="timer" aria-label="Time spent looking">
            {formatSeconds(elapsed)}
          </p>
        </div>
        <p className="challenge__count" aria-live="polite">
          {countText}
        </p>
        {canGiveUp ? (
          <div className="screen__actions challenge__give-up">
            <Button variant="secondary" onClick={giveUp}>
              Give up
            </Button>
          </div>
        ) : null}
        <p className="visually-hidden" aria-live="polite">
          {status}
        </p>
      </div>

      <div className="challenge__list card">
        <h2 className="challenge__list-title">Your chats</h2>
        {groups.map((group) => (
          <section key={group.key} className="challenge__month" aria-label={group.label}>
            <h3 className="challenge__month-title">{group.label}</h3>
            <ul className="challenge__chats">
              {group.chats.map((chat) => (
                <li key={chat.id}>
                  <button
                    type="button"
                    className={
                      shakeId === chat.id
                        ? "challenge__chat challenge__chat--shake"
                        : "challenge__chat"
                    }
                    onClick={() => tap(chat)}
                    onAnimationEnd={() => setShakeId((id) => (id === chat.id ? null : id))}
                  >
                    <span className="challenge__chat-title">{chat.title}</span>
                    <time className="challenge__chat-date" dateTime={chat.date}>
                      {dayLabel(chat.date)}
                    </time>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {matches.length === 0 ? (
          <p className="challenge__empty">
            No title has those words. Try fewer words, or different ones.
          </p>
        ) : null}
      </div>
    </section>
  );
}
