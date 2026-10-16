import { useEffect, useMemo, useRef } from "react";
import { Button } from "../components/Button";
import { Sidebar } from "../components/Sidebar";
import { assemble } from "../content/assemble";
import { getLibrary } from "../content/library";
import type { LibraryInterest } from "../content/types";
import { type Personality, useFlow } from "../state/flow";
import "./History.css";

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long" });

/** Used until the quiz sets a personality: a plain type and the first three interests. */
export function fallbackPersonality(
  library: readonly LibraryInterest[] = getLibrary(),
): Personality {
  return { type: "Curious Visitor", interests: library.slice(0, 3).map((e) => e.interest) };
}

/**
 * The library as the history sees it: the last chat of every thread of the chosen
 * interests is held back, so the chat step can offer it as the next question and
 * it becomes the visitor's own chat in that thread.
 */
export function holdBackLastChats(
  library: readonly LibraryInterest[],
  interests: readonly string[],
): LibraryInterest[] {
  const chosen = new Set(interests);
  return library.map((entry) =>
    chosen.has(entry.interest)
      ? {
          ...entry,
          threads: entry.threads.map((thread) => ({ ...thread, chats: thread.chats.slice(0, -1) })),
        }
      : entry,
  );
}

/** "a Weekend Explorer", "an Early Riser". */
export function withArticle(noun: string): string {
  return `${/^[aeiou]/i.test(noun) ? "an" : "a"} ${noun}`;
}

/** The sidebar's note, as the brief words it. */
export function historyNote(type: string): string {
  return `Nine months of chats, written for ${withArticle(type)}`;
}

/** Step 3: the nine-month history, assembled once and shown in a sidebar of our own design. */
export function History() {
  const { state, dispatch } = useFlow();
  const started = useRef(false);
  const { personality, history, now, seed } = state;

  useEffect(() => {
    if (started.current || history.length > 0) return;
    started.current = true;
    const library = getLibrary();
    const who = personality ?? fallbackPersonality(library);
    if (!personality) dispatch({ type: "setPersonality", personality: who });
    const fixedNow = now ?? new Date().toISOString();
    if (!now) dispatch({ type: "setNow", now: fixedNow });
    const chats = assemble(who.interests, seed, {
      now: new Date(fixedNow),
      library: holdBackLastChats(library, who.interests),
    });
    dispatch({ type: "setHistory", chats });
  }, [dispatch, personality, history.length, now, seed]);

  const type = personality?.type ?? "Curious Visitor";
  const span = useMemo(() => {
    if (history.length === 0) return null;
    const times = history.map((chat) => Date.parse(chat.date));
    return {
      first: MONTH_FORMAT.format(new Date(Math.min(...times))),
      last: MONTH_FORMAT.format(new Date(Math.max(...times))),
    };
  }, [history]);

  return (
    <section className="screen history" data-step="history" aria-labelledby="history-title">
      <div className="history__intro">
        <p className="screen__kicker">Step 3 of 8 · history</p>
        <h1 id="history-title">Your sidebar, nine months in</h1>
        {span ? (
          <p className="screen__lede">
            We wrote {history.length} chats the way {withArticle(type)} would ask them, from{" "}
            {span.first} to {span.last}. Have a scroll. Then start a new one, like you always do.
          </p>
        ) : (
          <p className="screen__lede">
            The chat library is still being written, so the sidebar is empty for now. You can still
            start a new chat.
          </p>
        )}
        <div className="screen__actions">
          <Button size="lg" onClick={() => dispatch({ type: "go", step: "chat" })}>
            Start a new chat
          </Button>
        </div>
      </div>
      <Sidebar
        className="history__sidebar"
        chats={history}
        now={now}
        note={historyNote(type)}
        emptyText="No chats yet: the library has not arrived."
      />
    </section>
  );
}
