import {
  type RefCallback,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { BundleCard, type BundleCardChat, bundleColour } from "../components/BundleCard";
import { Button } from "../components/Button";
import type { HistoryChat } from "../content/types";
import { type BundlingResult, bundleChats } from "../sorter/bundler";
import calibration from "../sorter/calibration.json";
import { sorter } from "../sorter/client";
import { loadLibraryEmbeddings } from "../sorter/embeddings";
import manifest from "../sorter/model-manifest.json";
import { useFlow } from "../state/flow";
import { usePrefersReducedMotion } from "../state/useMediaQuery";
import { useSorter } from "../state/useSorter";
import "./Reveal.css";

/* ---------- pure helpers (unit-tested in Reveal.test.ts) ---------- */

/** "48 s" under a minute, "mm:ss" from a minute up, "<1 s" when it rounds to nothing. */
export function formatDuration(ms: number): string {
  const seconds = Math.round(Math.max(0, ms) / 1000);
  if (seconds < 1) return "<1 s";
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

export interface Move {
  /** The step at which the chat settled where it is now. */
  at: number;
  bundleId: string | null;
  probability: number;
  suggested: boolean;
}

export interface ReplayPlan {
  /** Chat ids in the order the sorter met them. */
  order: string[];
  index: Map<string, number>;
  moves: Map<string, Move>;
  /** The step at which each bundle came into being. */
  bundleAt: Map<string, number>;
}

/**
 * Turn a bundling result into a plan the screen can replay step by step. A chat
 * that was left loose and later pulled into a new bundle moves twice: it is
 * loose from its own step, then joins the bundle at the step that created it.
 */
export function planReplay(result: BundlingResult): ReplayPlan {
  const order: string[] = [];
  const index = new Map<string, number>();
  const moves = new Map<string, Move>();
  const bundleAt = new Map<string, number>();
  for (const [j, step] of result.steps.entries()) {
    order.push(step.chatId);
    index.set(step.chatId, j);
    const suggested = step.action === "suggest";
    if (step.action === "leave" || step.targetId === null) {
      moves.set(step.chatId, {
        at: j,
        bundleId: null,
        probability: step.probability,
        suggested: false,
      });
    } else if (step.createdBundleId) {
      bundleAt.set(step.createdBundleId, j);
      const move: Move = {
        at: j,
        bundleId: step.createdBundleId,
        probability: step.probability,
        suggested,
      };
      moves.set(step.chatId, move);
      moves.set(step.targetId, move);
    } else {
      moves.set(step.chatId, {
        at: j,
        bundleId: step.targetId,
        probability: step.probability,
        suggested,
      });
    }
  }
  return { order, index, moves, bundleAt };
}

export type Place =
  | { where: "unsorted" }
  | { where: "loose" }
  | { where: "bundle"; bundleId: string };

/** Where a chat sits once the first k steps have played. */
export function locate(plan: ReplayPlan, chatId: string, k: number): Place {
  const i = plan.index.get(chatId);
  if (i === undefined || i >= k) return { where: "unsorted" };
  const move = plan.moves.get(chatId);
  if (move?.bundleId && move.at < k) return { where: "bundle", bundleId: move.bundleId };
  return { where: "loose" };
}

/** The chats that move at step k: the chat met then, plus a loose chat it forms a bundle with. */
export function moversAt(result: BundlingResult, k: number): string[] {
  const step = result.steps[k];
  if (!step) return [];
  return step.createdBundleId && step.targetId ? [step.chatId, step.targetId] : [step.chatId];
}

export interface LatencyStats {
  count: number;
  meanMs: number;
  p95Ms: number;
  maxMs: number;
  embedMs: number;
  decisionMs: number;
}

/** Per-decision latency, for the tech view. */
export function latencyStats(result: BundlingResult): LatencyStats {
  const times = result.steps.map((s) => s.ms).sort((a, b) => a - b);
  const count = times.length;
  const sum = times.reduce((acc, t) => acc + t, 0);
  const p95 = times[Math.min(count - 1, Math.floor(count * 0.95))] ?? 0;
  return {
    count,
    meanMs: count ? sum / count : 0,
    p95Ms: p95,
    maxMs: times[count - 1] ?? 0,
    embedMs: result.embedMs,
    decisionMs: result.decisionMs,
  };
}

/* ---------- the screen ---------- */

type Phase = "off" | "loading" | "sorting" | "find" | "done" | "error";

function byDate(a: HistoryChat, b: HistoryChat): number {
  return Date.parse(a.date) - Date.parse(b.date);
}

const shortDate = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

function formatMb(bytes: number): string {
  return (bytes / 1_048_576).toFixed(1);
}

/** Replay the whole sort in about four seconds, but never faster than the eye can follow. */
function stepInterval(total: number): number {
  return Math.max(18, Math.min(70, 4000 / Math.max(1, total)));
}

const SKIP_AFTER_MS = 30_000;

export function Reveal() {
  const { state, dispatch } = useFlow();
  const sorterState = useSorter();
  const reduce = usePrefersReducedMotion();

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

  const target = useMemo(() => {
    const wanted = state.challenge.targetId ? byId.get(state.challenge.targetId) : undefined;
    return wanted ?? state.myChats.at(-1) ?? chats.at(-1) ?? null;
  }, [state.challenge.targetId, state.myChats, byId, chats]);

  const alreadyBundled = state.bundling;
  const alreadyFound = state.challenge.afterMs !== null;
  const [result, setResult] = useState<BundlingResult | null>(alreadyBundled);
  const [phase, setPhase] = useState<Phase>(() =>
    alreadyBundled ? (alreadyFound ? "done" : "find") : "off",
  );
  const [k, setK] = useState(() => alreadyBundled?.steps.length ?? 0);
  const [status, setStatus] = useState("Runs here, in your browser. Nothing leaves this tab.");
  const [error, setError] = useState<string | null>(null);
  const [openIds, setOpenIds] = useState<ReadonlySet<string>>(() => new Set());
  const [foundId, setFoundId] = useState<string | null>(
    alreadyBundled && alreadyFound ? (target?.id ?? null) : null,
  );
  const [wrongId, setWrongId] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  /** True once the switch has been on for a while with no result: the visitor may carry on without bundles. */
  const [slow, setSlow] = useState(false);

  const kRef = useRef(k);
  const findStart = useRef<number | null>(null);
  const rows = useRef(new Map<string, HTMLElement>());
  const refCache = useRef(new Map<string, RefCallback<HTMLLIElement>>());
  const firstRects = useRef(new Map<string, DOMRect>());
  const findHeading = useRef<HTMLHeadingElement>(null);
  const scoreHeading = useRef<HTMLHeadingElement>(null);

  const plan = useMemo(() => (result ? planReplay(result) : null), [result]);
  const total = result?.steps.length ?? 0;
  const finding = phase === "find";
  const switchedOn = phase !== "off";

  /** One stable callback ref per chat id, shared by the long list, the bundles and the loose column. */
  const rowRef = useCallback((id: string): RefCallback<HTMLLIElement> => {
    let callback = refCache.current.get(id);
    if (!callback) {
      callback = (el) => {
        if (!el) return;
        rows.current.set(id, el);
        return () => {
          if (rows.current.get(id) === el) rows.current.delete(id);
        };
      };
      refCache.current.set(id, callback);
    }
    return callback;
  }, []);

  const run = useCallback(async () => {
    setError(null);
    try {
      setPhase("loading");
      setStatus("Fetching the small model. It stays in your browser.");
      await sorter.load();
      setPhase("sorting");
      setStatus(`Reading ${chats.length} chats, oldest first.`);
      const pre = await loadLibraryEmbeddings();
      const precomputed = pre && pre.model === manifest.id ? pre.vectors : null;
      const outcome = await bundleChats(chats, {
        calibration,
        embed: (texts) => sorter.embed(texts),
        precomputed,
      });
      kRef.current = 0;
      firstRects.current.clear();
      setK(0);
      setResult(outcome);
      dispatch({ type: "setBundling", result: outcome });
      setStatus(`Sorting ${outcome.steps.length} chats.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
      setPhase("error");
      setStatus("The sorter could not run.");
    }
  }, [chats, dispatch]);

  // Replay the decisions one at a time; all at once under reduced motion.
  useEffect(() => {
    if (phase !== "sorting" || !result) return;
    if (reduce) {
      kRef.current = total;
      setK(total);
      return;
    }
    const interval = stepInterval(total);
    let timer = 0;
    const tick = () => {
      const current = kRef.current;
      if (current >= total) return;
      for (const id of moversAt(result, current)) {
        const el = rows.current.get(id);
        if (el) firstRects.current.set(id, el.getBoundingClientRect());
      }
      kRef.current = current + 1;
      setK(current + 1);
      timer = window.setTimeout(tick, interval);
    };
    timer = window.setTimeout(tick, interval);
    return () => window.clearTimeout(timer);
  }, [phase, result, reduce, total]);

  // FLIP: a chat that just moved slides from where it was to where it is.
  // biome-ignore lint/correctness/useExhaustiveDependencies: runs after every replay step (k) to measure the new layout
  useLayoutEffect(() => {
    if (firstRects.current.size === 0) return;
    const pending = firstRects.current;
    firstRects.current = new Map();
    if (reduce) return;
    for (const [id, first] of pending) {
      const el = rows.current.get(id);
      if (!el || typeof el.animate !== "function") continue;
      const last = el.getBoundingClientRect();
      const dx = first.left - last.left;
      const dy = first.top - last.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      el.style.zIndex = "2";
      const animation = el.animate(
        [
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 0.6 },
          { transform: "translate(0, 0)", opacity: 1 },
        ],
        { duration: 420, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" },
      );
      const settle = () => {
        el.style.zIndex = "";
      };
      animation.finished.then(settle, settle);
    }
  }, [k, reduce]);

  // When every chat has a place, pause a beat, then set the challenge again.
  useEffect(() => {
    if (phase !== "sorting" || !result || k < total) return;
    const looseCount = result.loose.length;
    setStatus(
      `Sorted ${total} chats into ${result.bundles.length} bundles. ${looseCount} stayed loose.`,
    );
    const timer = window.setTimeout(
      () => {
        setOpenIds(new Set());
        setPhase("find");
      },
      reduce ? 0 : 700,
    );
    return () => window.clearTimeout(timer);
  }, [phase, result, k, total, reduce]);

  // The second half of the challenge: start the clock and move focus to the task.
  useEffect(() => {
    if (phase !== "find") return;
    if (findStart.current === null) findStart.current = performance.now();
    findHeading.current?.focus();
    const start = findStart.current;
    const timer = window.setInterval(() => setElapsedMs(performance.now() - start), 250);
    return () => window.clearInterval(timer);
  }, [phase]);

  useEffect(() => {
    if (phase === "done") scoreHeading.current?.focus();
  }, [phase]);

  // A stalled download or a very slow device must not strand the visitor: after a while, offer a way on.
  const busy = phase === "loading" || phase === "sorting";
  useEffect(() => {
    if (!busy) return;
    const timer = window.setTimeout(() => setSlow(true), SKIP_AFTER_MS);
    return () => {
      window.clearTimeout(timer);
      setSlow(false);
    };
  }, [busy]);

  useEffect(() => {
    if (!wrongId) return;
    const timer = window.setTimeout(() => setWrongId(null), 900);
    return () => window.clearTimeout(timer);
  }, [wrongId]);

  const flip = () => {
    if (phase !== "off") return;
    void run();
  };

  const toggleBundle = (id: string, open: boolean) => {
    setOpenIds((current) => {
      const next = new Set(current);
      if (open) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const pick = (chat: HistoryChat) => {
    if (phase !== "find" || !target) return;
    if (chat.id === target.id) {
      const ms = performance.now() - (findStart.current ?? performance.now());
      dispatch({ type: "setChallengeTime", which: "after", ms });
      setFoundId(chat.id);
      setPhase("done");
      setStatus(`Found it in ${formatDuration(ms)}.`);
    } else {
      setWrongId(chat.id);
      setStatus("Not that one. Try another bundle.");
    }
  };

  // What the board shows after k steps.
  const view = useMemo(() => {
    if (!plan || !result) {
      return { unsorted: chats, bundles: [] as BoardBundle[], loose: [] as BundleCardChat[] };
    }
    const members = new Map<string, BundleCardChat[]>();
    const loose: BundleCardChat[] = [];
    for (const id of plan.order.slice(0, k)) {
      const chat = byId.get(id);
      if (!chat) continue;
      const place = locate(plan, id, k);
      if (place.where === "bundle") {
        const move = plan.moves.get(id);
        const list = members.get(place.bundleId) ?? [];
        list.push({ chat, probability: move?.probability, suggested: move?.suggested });
        members.set(place.bundleId, list);
      } else if (place.where === "loose") {
        loose.push({ chat });
      }
    }
    const bundles: BoardBundle[] = [];
    for (const [i, bundle] of result.bundles.entries()) {
      if ((plan.bundleAt.get(bundle.id) ?? Number.POSITIVE_INFINITY) < k) {
        bundles.push({
          id: bundle.id,
          name: bundle.name,
          colour: bundleColour(i),
          chats: members.get(bundle.id) ?? [],
        });
      }
    }
    const unsorted = plan.order
      .slice(k)
      .map((id) => byId.get(id))
      .filter((chat): chat is HistoryChat => chat !== undefined);
    return { unsorted, bundles, loose };
  }, [plan, result, k, byId, chats]);

  const foundBundleId = foundId && result ? (result.placements[foundId]?.bundleId ?? null) : null;
  const stats = useMemo(() => (result ? latencyStats(result) : null), [result]);
  const showList =
    phase === "off" || phase === "loading" || phase === "sorting" || phase === "error";
  const progress = sorterState.progress;
  const canSkip = finding && elapsedMs >= SKIP_AFTER_MS;
  useEffect(() => {
    if (canSkip) setStatus("Still looking? You can skip the hunt.");
  }, [canSkip]);

  if (chats.length === 0) {
    return (
      <section className="screen reveal" data-step="reveal" aria-labelledby="reveal-title">
        <p className="screen__kicker">Step 7 of 8 · reveal</p>
        <h1 id="reveal-title">Nine months of chats. One switch.</h1>
        <p className="screen__lede">
          There is nothing to bundle yet: the history is empty. Take the quiz first, or carry
          straight on.
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
    <section
      className="screen reveal"
      data-step="reveal"
      data-phase={phase}
      aria-labelledby="reveal-title"
    >
      <p className="screen__kicker">Step 7 of 8 · reveal</p>
      <h1 id="reveal-title">Nine months of chats. One switch.</h1>
      <p className="screen__lede">
        A small open model runs here in your browser and sorts every chat into bundles. The rules
        are simple: file what it is sure of, suggest what it half-knows, leave the rest alone.
      </p>

      <div className="reveal__switchbar card">
        <button
          type="button"
          role="switch"
          aria-checked={switchedOn}
          aria-describedby="reveal-status"
          className="bundle-switch"
          onClick={flip}
        >
          <span className="bundle-switch__track" aria-hidden="true">
            <span className="bundle-switch__knob" />
          </span>
          <span className="bundle-switch__label">Bundle my chats</span>
        </button>
        <p id="reveal-status" className="reveal__status" aria-live="polite">
          {status}
        </p>
        {phase === "loading" && (
          <div className="reveal__download">
            <progress
              className="reveal__progress"
              aria-label="Model download"
              value={progress.total > 0 ? progress.loaded : undefined}
              max={progress.total > 0 ? progress.total : undefined}
            />
            <p className="reveal__download-text">
              {progress.total > 0
                ? `${formatMb(progress.loaded)} of ${formatMb(progress.total)} MB`
                : sorterState.status === "ready"
                  ? "Warming up"
                  : "Connecting"}
            </p>
          </div>
        )}
        {phase === "sorting" && k < total && (
          <p className="reveal__counter" aria-hidden="true">
            {k} of {total} sorted
          </p>
        )}
        {busy && slow && (
          <div className="screen__actions reveal__slow">
            <Button variant="ghost" onClick={() => dispatch({ type: "next" })}>
              Carry on without bundling
            </Button>
          </div>
        )}
      </div>

      {phase === "error" && (
        <div className="reveal__error card" role="alert">
          <h2>The sorter could not run</h2>
          <p className="reveal__error-text">{error}</p>
          <p className="reveal__hint">
            {manifest.source === "local"
              ? "The model is served from this site; "
              : "The model is fetched once from huggingface.co; "}
            nothing you typed or picked is sent anywhere. Try again, or carry on without the
            bundles.
          </p>
          <div className="screen__actions">
            <Button onClick={() => void run()}>Try again</Button>
            <Button variant="secondary" onClick={() => dispatch({ type: "next" })}>
              Carry on anyway
            </Button>
          </div>
        </div>
      )}

      <div className={`reveal__board${showList ? "" : " reveal__board--wide"}`}>
        {showList && (
          // biome-ignore lint/a11y/noNoninteractiveTabindex: the long list scrolls, so it must be reachable from the keyboard
          <section className="reveal__list card" aria-labelledby="reveal-list-title" tabIndex={0}>
            <h2 id="reveal-list-title" className="reveal__list-title">
              <span>The long list</span>
              <span className="reveal__count">{view.unsorted.length}</span>
            </h2>
            {view.unsorted.length > 0 ? (
              <ul className="reveal__rows">
                {view.unsorted.map((chat, i) => (
                  <li
                    key={chat.id}
                    ref={rowRef(chat.id)}
                    className="reveal__row"
                    data-current={phase === "sorting" && i === 0 ? "" : undefined}
                  >
                    <span className="reveal__row-title">{chat.title}</span>
                    <time className="reveal__row-date" dateTime={chat.date}>
                      {shortDate.format(new Date(chat.date))}
                    </time>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="reveal__hint">Every chat has a place.</p>
            )}
          </section>
        )}

        <div className="reveal__right">
          {finding && target && (
            <div className="reveal__find card">
              <h2 id="reveal-find-title" ref={findHeading} tabIndex={-1}>
                Now find it again
              </h2>
              <p className="reveal__task">
                The chat where you asked about <strong>{target.paraphrase}</strong>. Open a bundle
                and tap the chat.
              </p>
              <p className="reveal__timer" role="timer" aria-label="Time spent looking">
                {formatDuration(elapsedMs)}
              </p>
              {canSkip && (
                <div className="screen__actions">
                  <Button variant="ghost" onClick={() => dispatch({ type: "next" })}>
                    Skip the hunt
                  </Button>
                </div>
              )}
            </div>
          )}

          {phase === "done" && (
            <div className="reveal__score card">
              <h2 id="reveal-score-title" ref={scoreHeading} tabIndex={-1}>
                Found it.
              </h2>
              <p className="reveal__headline">
                Before:{" "}
                <em>
                  {state.challenge.beforeMs === null
                    ? "not timed"
                    : state.challenge.gaveUp
                      ? `gave up after ${formatDuration(state.challenge.beforeMs)}`
                      : formatDuration(state.challenge.beforeMs)}
                </em>
                . After:{" "}
                <em>
                  {state.challenge.afterMs === null ? "—" : formatDuration(state.challenge.afterMs)}
                </em>
                .
              </p>
              <p className="reveal__moral">
                Same chats. Same you. The only thing that changed was the switch.
              </p>
              {state.techView && stats && (
                <p className="reveal__tech">
                  {stats.count} decisions · mean {stats.meanMs.toFixed(2)} ms · p95{" "}
                  {stats.p95Ms.toFixed(2)} ms · max {stats.maxMs.toFixed(2)} ms · embedding{" "}
                  {Math.round(stats.embedMs)} ms · {sorterState.ready?.device ?? "device unknown"} ·
                  T {calibration.temperature}, file ≥ {calibration.fileCutoff}, suggest ≥{" "}
                  {calibration.suggestCutoff}
                </p>
              )}
              <div className="screen__actions">
                <Button size="lg" onClick={() => dispatch({ type: "next" })}>
                  Carry on
                </Button>
              </div>
            </div>
          )}

          {(view.bundles.length > 0 || view.loose.length > 0) && (
            <div className="reveal__bundles">
              {view.bundles.map((bundle) => (
                <BundleCard
                  key={bundle.id}
                  id={bundle.id}
                  name={bundle.name}
                  colour={bundle.colour}
                  chats={bundle.chats}
                  collapsible={finding}
                  open={finding ? openIds.has(bundle.id) : true}
                  onToggle={(open) => toggleBundle(bundle.id, open)}
                  onChatSelect={finding ? pick : undefined}
                  selectedChatId={foundId}
                  wrongChatId={wrongId}
                  rowRef={rowRef}
                  className={phase === "done" && foundBundleId === bundle.id ? "is-found" : ""}
                />
              ))}
              {view.loose.length > 0 && (
                <BundleCard
                  id="loose"
                  name="Loose"
                  colour="loose"
                  chats={view.loose}
                  collapsible={finding}
                  open={finding ? openIds.has("loose") : true}
                  onToggle={(open) => toggleBundle("loose", open)}
                  onChatSelect={finding ? pick : undefined}
                  selectedChatId={foundId}
                  wrongChatId={wrongId}
                  rowRef={rowRef}
                  className={`reveal__loose${phase === "done" && foundId && foundBundleId === null ? " is-found" : ""}`}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

interface BoardBundle {
  id: string;
  name: string;
  colour: ReturnType<typeof bundleColour>;
  chats: BundleCardChat[];
}
