import { type FormEvent, useCallback, useEffect, useId, useRef, useState } from "react";
import { Button } from "../components/Button";
import { Sidebar, SidebarDrawer } from "../components/Sidebar";
import { Typing } from "../components/Typing";
import { mulberry32, shuffle } from "../content/assemble";
import { getLibrary } from "../content/library";
import type { HistoryChat, LibraryChat, LibraryInterest } from "../content/types";
import { useFlow } from "../state/flow";
import { useMediaQuery } from "../state/useMediaQuery";
import "./Chat.css";

/** How many ready-made questions the chat offers at once. */
export const MAX_READY_QUESTIONS = 5;
/** After this many taps the visitor may fast-forward. */
export const TAPS_BEFORE_FORWARD = 3;
/** The reply to anything typed. Typed text lives in this component's state only. */
export const TYPED_REPLY =
  "This demo only answers its ready-made questions, so nothing you type is sent anywhere: it stays in this tab. Tap one of the questions to carry on.";
/** Minutes between the visitor's own chats, all dated "today". */
const MINUTES_BETWEEN_TAPS = 2;

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
});

export interface ReadyQuestion {
  chat: LibraryChat;
  interest: string;
  threadId: string;
}

/**
 * The next unused chat of up to `max` different threads of the chosen interests:
 * threads are ordered by the seed and interleaved across interests, so the
 * questions span the visitor's interests. Threads with no unused chat are skipped.
 */
export function pickReadyQuestions(
  library: readonly LibraryInterest[],
  interests: readonly string[],
  used: ReadonlySet<string>,
  seed: number,
  max = MAX_READY_QUESTIONS,
): ReadyQuestion[] {
  const random = mulberry32(seed ^ 0x9e3779b9);
  const perInterest = interests
    .map((id) => library.find((entry) => entry.interest === id))
    .filter((entry): entry is LibraryInterest => entry !== undefined)
    .map((entry) =>
      shuffle(entry.threads, random)
        .map((thread) => {
          const chat = thread.chats.find((c) => !used.has(c.id));
          return chat ? { chat, interest: entry.interest, threadId: thread.id } : null;
        })
        .filter((q): q is ReadyQuestion => q !== null),
    );
  const out: ReadyQuestion[] = [];
  for (let round = 0; out.length < max; round += 1) {
    let any = false;
    for (const list of perInterest) {
      const question = list[round];
      if (!question) continue;
      any = true;
      if (out.length < max) out.push(question);
    }
    if (!any) break;
  }
  return out;
}

/** The visitor's own chat for a tapped question, dated a few minutes after the fixed now. */
export function ownChat(question: ReadyQuestion, now: string, tapIndex: number): HistoryChat {
  const date = new Date(Date.parse(now) + tapIndex * MINUTES_BETWEEN_TAPS * 60_000).toISOString();
  return {
    id: question.chat.id,
    libraryId: question.chat.id,
    title: question.chat.title,
    question: question.chat.question,
    reply: question.chat.reply,
    paraphrase: question.chat.paraphrase,
    interest: question.interest,
    threadId: question.threadId,
    date,
    mine: true,
  };
}

interface Message {
  id: number;
  role: "you" | "reply";
  text: string;
  typing: boolean;
}

function transcript(chats: readonly HistoryChat[]): Message[] {
  return chats.flatMap((chat, index) => [
    { id: index * 2, role: "you" as const, text: chat.question, typing: false },
    { id: index * 2 + 1, role: "reply" as const, text: chat.reply, typing: false },
  ]);
}

function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Step 4: a new chat with ready-made questions to tap; typed text never leaves the browser. */
export function Chat() {
  const { state, dispatch } = useFlow();
  const desktop = useMediaQuery("(min-width: 48rem)");
  const inputId = useId();
  const drawerId = useId();

  const [now] = useState(() => state.now ?? new Date().toISOString());
  const [ready] = useState(() => {
    const used = new Set([...state.history, ...state.myChats].map((chat) => chat.libraryId));
    return pickReadyQuestions(getLibrary(), state.personality?.interests ?? [], used, state.seed);
  });
  const [messages, setMessages] = useState<Message[]>(() => transcript(state.myChats));
  const [draft, setDraft] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const nextId = useRef(messages.length);
  const listRef = useRef<HTMLOListElement>(null);
  const chipsRef = useRef<HTMLFieldSetElement>(null);
  const forwardRef = useRef<HTMLDivElement>(null);
  const focusChipAt = useRef<number | null>(null);

  const asked = new Set(state.myChats.map((chat) => chat.libraryId));
  const chips = ready.filter((question) => !asked.has(question.chat.id));
  const taps = state.myChats.length;
  const canForward = taps >= TAPS_BEFORE_FORWARD || chips.length === 0;
  const allChats = [...state.history, ...state.myChats];

  const say = useCallback((you: string, reply: string) => {
    setMessages((previous) => [
      ...previous.map((message) => ({ ...message, typing: false })),
      { id: nextId.current++, role: "you", text: you, typing: false },
      { id: nextId.current++, role: "reply", text: reply, typing: true },
    ]);
  }, []);

  const finish = useCallback((id: number) => {
    setMessages((previous) =>
      previous.map((message) => (message.id === id ? { ...message, typing: false } : message)),
    );
  }, []);

  const ask = (question: ReadyQuestion, index: number) => {
    dispatch({ type: "addMyChat", chat: ownChat(question, now, taps + 1) });
    say(question.chat.question, question.chat.reply);
    focusChipAt.current = index;
  };

  const send = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    say(text, TYPED_REPLY);
    setDraft("");
  };

  // Keep the newest words in view while a reply types itself out.
  useEffect(() => {
    const list = listRef.current;
    if (!list || typeof MutationObserver === "undefined") return;
    const observer = new MutationObserver(() => {
      list.scrollTop = list.scrollHeight;
    });
    observer.observe(list, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, []);

  // After a tap the chip is gone: move focus to the next one, or to the fast-forward button.
  useEffect(() => {
    const index = focusChipAt.current;
    if (index === null) return;
    focusChipAt.current = null;
    const buttons = chipsRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? [];
    const target =
      buttons[Math.min(index, buttons.length - 1)] ?? forwardRef.current?.querySelector("button");
    target?.focus();
  });

  const sidebar = (
    <Sidebar
      chats={allChats}
      now={now}
      note={allChats.length > 0 ? "Your new chat lands at the top." : undefined}
    />
  );

  return (
    <section className="screen chat" data-step="chat" aria-labelledby="chat-title">
      <div className="chat__top">
        <p className="screen__kicker">Step 4 of 8 · chat</p>
        <h1 id="chat-title">Ask something new</h1>
        <p className="screen__lede">
          Tap a question, or type your own. Nothing you type leaves this tab.
        </p>
      </div>

      {desktop ? (
        <div className="chat__side">{sidebar}</div>
      ) : (
        <SidebarDrawer
          id={drawerId}
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          chats={allChats}
          now={now}
        />
      )}

      <div className="chat__panel">
        <div className="chat__panel-head">
          {!desktop && (
            <button
              type="button"
              className="chat__toggle"
              aria-expanded={drawerOpen}
              aria-controls={drawerId}
              onClick={() => setDrawerOpen(true)}
            >
              <span className="chat__toggle-icon" aria-hidden="true" />
              Your chats
              <span className="chat__toggle-count">{allChats.length}</span>
            </button>
          )}
          <p className="chat__panel-title">
            New chat · <time dateTime={now.slice(0, 10)}>{DATE_FORMAT.format(new Date(now))}</time>
          </p>
        </div>

        <ol
          ref={listRef}
          className="chat__messages"
          aria-live="polite"
          aria-label="Conversation"
          // The transcript scrolls once it has messages, so it is then reachable from the keyboard.
          tabIndex={messages.length > 0 ? 0 : undefined}
        >
          {messages.map((message) => (
            <li key={message.id} className={cx("msg", `msg--${message.role}`)}>
              <span className="msg__who">{message.role === "you" ? "You" : "Assistant"}</span>
              {message.typing ? (
                <Typing text={message.text} onDone={() => finish(message.id)} />
              ) : (
                <span>{message.text}</span>
              )}
            </li>
          ))}
        </ol>

        <div className="chat__bottom">
          {messages.length === 0 && chips.length > 0 && (
            <p className="chat__hint">Tap a question to start.</p>
          )}
          {chips.length > 0 ? (
            <fieldset ref={chipsRef} className="chat__chips">
              <legend className="visually-hidden">Ready-made questions</legend>
              {chips.map((question, index) => (
                <button
                  key={question.chat.id}
                  type="button"
                  className="chip"
                  aria-label={question.chat.question}
                  onClick={() => ask(question, index)}
                >
                  <span className="chip__text" aria-hidden="true">
                    {question.chat.question}
                  </span>
                </button>
              ))}
            </fieldset>
          ) : (
            <p className="chat__hint">
              {taps > 0
                ? "That's every question for today."
                : "No ready-made questions yet: the library has not arrived."}
            </p>
          )}

          {canForward && (
            <div ref={forwardRef} className="chat__forward">
              <p className="chat__forward-text">
                {taps > 0
                  ? "Good questions. Now let's jump ahead and watch the pile grow."
                  : "Let's jump ahead and watch the pile grow."}
              </p>
              <Button size="lg" onClick={() => dispatch({ type: "go", step: "months" })}>
                Fast-forward a few months
              </Button>
            </div>
          )}

          <form className="chat__composer" onSubmit={send}>
            <label className="chat__label" htmlFor={inputId}>
              Or type your own
            </label>
            <input
              id={inputId}
              className="chat__input"
              type="text"
              value={draft}
              maxLength={240}
              autoComplete="off"
              enterKeyHint="send"
              onChange={(event) => setDraft(event.target.value)}
            />
            <Button type="submit" variant="secondary" disabled={draft.trim() === ""}>
              Send
            </Button>
          </form>
        </div>
      </div>
    </section>
  );
}
