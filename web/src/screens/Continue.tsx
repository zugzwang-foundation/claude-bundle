import { useEffect, useMemo, useRef, useState } from "react";
import { BundleCard, type BundleCardChat, bundleColour } from "../components/BundleCard";
import { Button } from "../components/Button";
import { ContinuationReply } from "../components/ContinuationReply";
import { APP_NAME } from "../config";
import {
  bundleChatIdsFor,
  type ContinuationPart,
  fillContinuationParts,
  pickContinuation,
  SLOT_PATTERN,
} from "../content/continuation";
import { getLibrary } from "../content/library";
import type { HistoryChat, LibraryInterest } from "../content/types";
import type { BundlingResult } from "../sorter/bundler";
import { useFlow } from "../state/flow";
import { usePrefersReducedMotion } from "../state/useMediaQuery";
import { planReplay } from "./Reveal";
import "./Continue.css";

/* ---------- pure helpers (unit-tested in Continue.test.ts) ---------- */

/** Used when the found chat has no thread of its own (a one-off) but sits in a bundle with others. */
export const FALLBACK_CONTINUATION = {
  question: "ok im back, can you pull together where we got to?",
  reply:
    "Happily. Reading back through this bundle, the thread runs from {{chat:1}} through {{chat:2}} to {{chat:3}}, and the questions got sharper each time, which usually means the basics have stuck. Tell me which part still feels wobbly and we will pick it up from there.",
};

/** Used when a one-off sits on its own: there is nothing earlier to lean on. */
export const LOOSE_CONTINUATION = {
  question: "ok im back, where were we?",
  reply:
    "Right here. This chat sits on its own, so there is no earlier thread to lean on: everything we need is in the question above. Tell me what has changed since, and we will pick it up from there.",
};

export interface ContinuationPlan {
  question: string;
  reply: string;
  /** The reply with its slots filled, kept as parts so each title can be highlighted. */
  parts: ContinuationPart[];
  text: string;
  source: "thread" | "fallback" | "loose";
  threadId: string | null;
  topic: string | null;
  /** Slots in the reply, and how many ended up naming a chat from the bundle. */
  slots: number;
  named: number;
  /** The ids of the chats in the found chat's bundle (just the chat itself when loose). */
  bundleChatIds: Set<string>;
}

function byDate(a: HistoryChat, b: HistoryChat): number {
  return Date.parse(a.date) - Date.parse(b.date) || a.id.localeCompare(b.id);
}

/**
 * What the found chat's follow-up says, given what the sorter actually put in its
 * bundle. The thread's own continuation leads; its slots are filled from the
 * thread's chats that are in the bundle, then from the bundle's other members,
 * and dropped when the bundle offers nothing. The found chat never names itself.
 */
export function planContinuation(
  found: HistoryChat,
  library: readonly LibraryInterest[],
  chats: readonly HistoryChat[],
  bundling: Pick<BundlingResult, "bundles"> | null,
): ContinuationPlan {
  const bundleChatIds = bundleChatIdsFor(found.id, bundling);
  const others = chats
    .filter((chat) => bundleChatIds.has(chat.id) && chat.id !== found.id)
    .sort(byDate);
  const nameable = new Set(others.map((chat) => chat.id));
  const picked = pickContinuation(found, library, chats);

  let question: string;
  let reply: string;
  let threadChats: HistoryChat[];
  let source: ContinuationPlan["source"];
  if (picked) {
    source = "thread";
    question = picked.question;
    reply = picked.reply;
    // Thread chats first, so slot N is the thread's N-th chat; the bundle's other members
    // follow, so a slot whose chat the sorter filed elsewhere still names something real.
    const seen = new Set(picked.threadChats.map((chat) => chat.id));
    threadChats = [...picked.threadChats, ...others.filter((chat) => !seen.has(chat.id))];
  } else if (others.length > 0) {
    source = "fallback";
    question = FALLBACK_CONTINUATION.question;
    reply = FALLBACK_CONTINUATION.reply;
    threadChats = others;
  } else {
    source = "loose";
    question = LOOSE_CONTINUATION.question;
    reply = LOOSE_CONTINUATION.reply;
    threadChats = [];
  }

  const parts = fillContinuationParts(reply, threadChats, nameable);
  return {
    question,
    reply,
    parts,
    text: parts.map((part) => part.text).join(""),
    source,
    threadId: picked?.threadId ?? null,
    topic: picked?.topic ?? null,
    slots: [...reply.matchAll(SLOT_PATTERN)].length,
    named: parts.filter((part) => part.kind === "title").length,
    bundleChatIds,
  };
}

/* ---------- the screen ---------- */

type Phase = "ask" | "thinking" | "replied";

/** How long the reply "thinks" before it appears; nothing under reduced motion. */
const THINK_MS = 1100;
const NO_CHATS: readonly HistoryChat[] = [];

const longDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long" });

export function Continue() {
  const { state, dispatch } = useFlow();
  const reduce = usePrefersReducedMotion();
  const [phase, setPhase] = useState<Phase>("ask");
  const replyRef = useRef<HTMLLIElement>(null);

  const chats = useMemo(() => {
    const seen = new Set<string>();
    const all: HistoryChat[] = [];
    for (const chat of [...state.history, ...state.myChats]) {
      if (seen.has(chat.id)) continue;
      seen.add(chat.id);
      all.push(chat);
    }
    return all.sort(byDate);
  }, [state.history, state.myChats]);
  const byId = useMemo(() => new Map(chats.map((chat) => [chat.id, chat])), [chats]);

  const found = useMemo(() => {
    const wanted = state.challenge.targetId ? byId.get(state.challenge.targetId) : undefined;
    return wanted ?? state.myChats.at(-1) ?? chats.at(-1) ?? null;
  }, [state.challenge.targetId, state.myChats, byId, chats]);

  const bundling = state.bundling;
  const bundleIndex = useMemo(
    () =>
      found && bundling ? bundling.bundles.findIndex((b) => b.chatIds.includes(found.id)) : -1,
    [found, bundling],
  );
  const bundle = bundleIndex >= 0 ? (bundling?.bundles[bundleIndex] ?? null) : null;

  const members = useMemo(() => {
    if (bundle) {
      return bundle.chatIds
        .map((id) => byId.get(id))
        .filter((chat): chat is HistoryChat => chat !== undefined)
        .sort(byDate);
    }
    return found ? [found] : [];
  }, [bundle, byId, found]);

  const replay = useMemo(() => (bundling ? planReplay(bundling) : null), [bundling]);
  const cardChats = useMemo<BundleCardChat[]>(
    () =>
      members.map((chat) => {
        const move = replay?.moves.get(chat.id);
        return bundle && move?.bundleId
          ? { chat, probability: move.probability, suggested: move.suggested }
          : { chat };
      }),
    [members, replay, bundle],
  );

  const continuation = useMemo(
    () => (found ? planContinuation(found, getLibrary(), chats, bundling) : null),
    [found, chats, bundling],
  );

  useEffect(() => {
    if (phase !== "thinking") return;
    const timer = window.setTimeout(() => setPhase("replied"), reduce ? 0 : THINK_MS);
    return () => window.clearTimeout(timer);
  }, [phase, reduce]);

  useEffect(() => {
    if (phase !== "ask") replyRef.current?.scrollIntoView({ block: "nearest" });
  }, [phase]);

  if (!found || !continuation) {
    return (
      <section className="screen continue" data-step="continue" aria-labelledby="continue-title">
        <p className="screen__kicker">Step 8 of 8 · continue</p>
        <h1 id="continue-title">Carry on where you left off</h1>
        <p className="screen__lede">
          Nothing to open yet: the history is empty. Start over to take the quiz.
        </p>
        <div className="screen__actions">
          <Button size="lg" onClick={() => dispatch({ type: "reset" })}>
            Start over
          </Button>
        </div>
      </section>
    );
  }

  const related = members.length - 1;
  const context = bundle
    ? `Opened inside ‘${bundle.name}’, with ${related} related ${related === 1 ? "chat" : "chats"} for context.`
    : bundling
      ? "Opened on its own: the sorter left this one loose."
      : "Opened on its own: the chats were never bundled.";
  const sourceLabel =
    continuation.source === "thread"
      ? `thread ${continuation.threadId}`
      : continuation.source === "fallback"
        ? "the bundle fallback"
        : "the loose fallback";

  return (
    <section className="screen continue" data-step="continue" aria-labelledby="continue-title">
      <p className="screen__kicker">Step 8 of 8 · continue</p>
      <h1 id="continue-title">Carry on where you left off</h1>
      <p className="screen__lede">
        The chat opens inside its bundle, and the reply knows what else is in there.
      </p>

      <div className="continue__board">
        <BundleCard
          id={bundle?.id ?? "loose"}
          name={bundle?.name ?? "Loose"}
          colour={bundle ? bundleColour(bundleIndex) : "loose"}
          chats={cardChats}
          selectedChatId={found.id}
          animateRows
          headingLevel={2}
          className="continue__bundle"
        >
          {!bundle && (
            <p className="continue__note">
              {bundling
                ? "Nothing in nine months was close enough, so the sorter left this chat alone rather than guess."
                : "Flip the switch on the previous step to see where this chat would land."}
            </p>
          )}
        </BundleCard>

        <article className="continue__chat card" aria-labelledby="continue-chat-title">
          <header className="continue__chat-head">
            <h2 id="continue-chat-title">{found.title}</h2>
            <p className="continue__context">{context}</p>
          </header>
          <ol className="continue__turns">
            <li className="continue__turn continue__turn--you">
              <span className="continue__who">You, {longDate.format(new Date(found.date))}</span>
              <p>{found.question}</p>
            </li>
            <li className="continue__turn continue__turn--reply">
              <span className="continue__who">Reply</span>
              <p>{found.reply}</p>
            </li>
            {phase !== "ask" && (
              <li className="continue__turn continue__turn--you">
                <span className="continue__who">You, today</span>
                <p>{continuation.question}</p>
              </li>
            )}
            {phase !== "ask" && (
              <li
                className="continue__turn continue__turn--reply"
                ref={replyRef}
                aria-live="polite"
              >
                <span className="continue__who">Reply</span>
                {phase === "thinking" ? (
                  <p className="continue__thinking">
                    <span className="visually-hidden">Thinking…</span>
                    <span className="continue__dots" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                    </span>
                  </p>
                ) : (
                  <ContinuationReply
                    reply={continuation.reply}
                    threadChats={NO_CHATS}
                    bundleChatIds={continuation.bundleChatIds}
                    parts={continuation.parts}
                    data-testid="continue-reply"
                  />
                )}
              </li>
            )}
          </ol>
          {phase === "ask" && (
            <div className="continue__ask">
              <p id="continue-ask-label" className="continue__ask-label">
                Ready-made follow-up
              </p>
              <button
                type="button"
                className="continue__question"
                aria-describedby="continue-ask-label"
                onClick={() => setPhase("thinking")}
              >
                {continuation.question}
              </button>
            </div>
          )}
          {phase === "replied" && (
            <p className="continue__closing">
              That is {APP_NAME}: a small open model in your browser, sorting your chats so any of
              them can be picked up again.
            </p>
          )}
        </article>
      </div>

      {state.techView && (
        <p className="continue__tech">
          Continuation from {sourceLabel} · {continuation.slots}{" "}
          {continuation.slots === 1 ? "slot" : "slots"}: {continuation.named} named from the bundle,{" "}
          {continuation.slots - continuation.named} dropped · bundle of {members.length}
        </p>
      )}

      <div className="screen__actions">
        <Button
          size="lg"
          variant={phase === "replied" ? "primary" : "secondary"}
          onClick={() => dispatch({ type: "reset" })}
        >
          Start over
        </Button>
      </div>
    </section>
  );
}
