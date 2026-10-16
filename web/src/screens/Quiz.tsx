import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "../components/Button";
import {
  buildResult,
  INTEREST_LABELS,
  indefiniteArticle,
  QUESTIONS,
  type QuizQuestion,
} from "../content/quiz";
import { sorter } from "../sorter/client";
import { useFlow } from "../state/flow";
import { usePrefersReducedMotion } from "../state/useMediaQuery";
import { useSorter } from "../state/useSorter";
import "./Quiz.css";

const TOTAL = QUESTIONS.length;
/** How long a tapped card stays highlighted before the next question arrives. */
const ADVANCE_DELAY_MS = 260;

/**
 * Step 2: seven single-tap questions, then an original personality type with
 * three to five interests. The sorter model starts downloading on mount, so it
 * is usually ready long before the reveal.
 */
export function Quiz() {
  const { state, dispatch } = useFlow();
  const reduceMotion = usePrefersReducedMotion();
  const answeredCount = QUESTIONS.filter((q) => state.quizAnswers[q.id]).length;
  const [index, setIndex] = useState(() => Math.min(answeredCount, TOTAL));
  const [pendingOption, setPendingOption] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const advanceTimer = useRef<number | null>(null);

  // The model downloads while the visitor taps. load() is idempotent.
  useEffect(() => {
    sorter.load().catch(() => undefined);
  }, []);

  // Each new question or the result announces itself and takes focus.
  // biome-ignore lint/correctness/useExhaustiveDependencies: focus must move every time the question index changes
  useEffect(() => {
    headingRef.current?.focus();
  }, [index]);

  useEffect(
    () => () => {
      if (advanceTimer.current !== null) window.clearTimeout(advanceTimer.current);
    },
    [],
  );

  const question: QuizQuestion | undefined = QUESTIONS[index];

  // Keys 1 to 4 choose a card from anywhere on the page, not only inside the group.
  useEffect(() => {
    if (!question) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.defaultPrevented) return;
      if (isTextField(event.target)) return;
      const digit = Number.parseInt(event.key, 10);
      const option = question?.options[digit - 1];
      if (!option) return;
      event.preventDefault();
      pick(option.id);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  function goTo(nextIndex: number) {
    if (advanceTimer.current !== null) window.clearTimeout(advanceTimer.current);
    advanceTimer.current = null;
    setPendingOption(null);
    setIndex(Math.max(0, Math.min(nextIndex, TOTAL)));
  }

  function pick(optionId: string) {
    if (!question || pendingOption !== null) return;
    dispatch({ type: "answer", questionId: question.id, optionId });
    if (reduceMotion) {
      goTo(index + 1);
      return;
    }
    setPendingOption(optionId);
    advanceTimer.current = window.setTimeout(() => {
      advanceTimer.current = null;
      setPendingOption(null);
      setIndex((i) => Math.min(i + 1, TOTAL));
    }, ADVANCE_DELAY_MS);
  }

  function back() {
    if (index === 0) dispatch({ type: "back" });
    else goTo(index - 1);
  }

  if (!question) {
    return (
      <QuizResult headingRef={headingRef} onRetake={() => goTo(0)} onBack={() => goTo(TOTAL - 1)} />
    );
  }

  const chosen = pendingOption ?? state.quizAnswers[question.id] ?? null;

  return (
    <section className="screen quiz" data-step="quiz" aria-labelledby="quiz-title">
      <div className="quiz__progress">
        <p className="screen__kicker" id="quiz-progress">
          Question {index + 1} of {TOTAL}
        </p>
        <div
          className="quiz__track"
          role="progressbar"
          aria-labelledby="quiz-progress"
          aria-valuemin={1}
          aria-valuemax={TOTAL}
          aria-valuenow={index + 1}
        >
          {QUESTIONS.map((q, i) => (
            <span
              key={q.id}
              className="quiz__segment"
              data-state={i < index ? "done" : i === index ? "current" : "todo"}
            />
          ))}
        </div>
      </div>

      <h1 id="quiz-title" className="quiz__question" ref={headingRef} tabIndex={-1}>
        {question.prompt}
      </h1>

      <QuizOptions
        key={question.id}
        question={question}
        chosen={chosen}
        locked={pendingOption !== null}
        onPick={pick}
      />

      <div className="quiz__nav">
        <Button variant="ghost" onClick={back}>
          Back
        </Button>
        <p className="quiz__hint" aria-hidden="true">
          Tap a card, or press 1 to 4
        </p>
      </div>

      <SorterLine />
    </section>
  );
}

interface QuizOptionsProps {
  question: QuizQuestion;
  chosen: string | null;
  locked: boolean;
  onPick: (optionId: string) => void;
}

/** Four big cards. Tab or the arrow keys move between them; Enter, Space or 1–4 choose. */
function QuizOptions({ question, chosen, locked, onPick }: QuizOptionsProps) {
  const groupRef = useRef<HTMLFieldSetElement>(null);

  function buttons(): HTMLButtonElement[] {
    return Array.from(groupRef.current?.querySelectorAll<HTMLButtonElement>("button") ?? []);
  }

  function onKeyDown(event: KeyboardEvent<HTMLFieldSetElement>) {
    const list = buttons();
    if (list.length === 0) return;
    const current = list.indexOf(document.activeElement as HTMLButtonElement);
    let next: number | null = null;
    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        next = current < 0 ? 0 : (current + 1) % list.length;
        break;
      case "ArrowUp":
      case "ArrowLeft":
        next = current < 0 ? list.length - 1 : (current - 1 + list.length) % list.length;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = list.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    list[next]?.focus();
  }

  return (
    <fieldset
      ref={groupRef}
      className="quiz__options"
      aria-labelledby="quiz-title"
      onKeyDown={onKeyDown}
    >
      {question.options.map((option, i) => {
        const selected = chosen === option.id;
        return (
          <button
            key={option.id}
            type="button"
            className="quiz__option"
            aria-pressed={selected}
            aria-disabled={locked && !selected ? true : undefined}
            onClick={() => {
              if (!locked) onPick(option.id);
            }}
          >
            <span className="quiz__option-key" aria-hidden="true">
              {i + 1}
            </span>
            <span className="quiz__option-text">{option.text}</span>
          </button>
        );
      })}
    </fieldset>
  );
}

interface QuizResultProps {
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  onRetake: () => void;
  onBack: () => void;
}

/** The ending: a type, one line about it, the chips, and the way into the story. */
function QuizResult({ headingRef, onRetake, onBack }: QuizResultProps) {
  const { state, dispatch } = useFlow();
  const result = useMemo(() => buildResult(state.quizAnswers), [state.quizAnswers]);
  const { type, interests } = result;

  function buildHistory() {
    // A retaken quiz with different interests starts the story again; the same answers keep it.
    const previous = state.personality?.interests ?? [];
    const changed =
      previous.length !== interests.length || previous.some((id, i) => id !== interests[i]);
    if (changed && state.history.length > 0) dispatch({ type: "clearStory" });
    dispatch({
      type: "setPersonality",
      personality: { type: type.name, interests: [...interests] },
    });
    dispatch({ type: "go", step: "history" });
  }

  return (
    <section className="screen quiz quiz--result" data-step="quiz" aria-labelledby="quiz-title">
      <p className="screen__kicker">Your type</p>
      <h1 id="quiz-title" className="quiz__type" ref={headingRef} tabIndex={-1}>
        <span className="quiz__type-lead">You're {indefiniteArticle(type.name)}</span>{" "}
        <span className="quiz__type-name">{type.name}</span>
      </h1>
      <p className="screen__lede quiz__tagline">{type.tagline}</p>

      <div className="quiz__interests">
        <p className="quiz__interests-label" id="quiz-interests">
          Your chats will be about
        </p>
        <ul className="quiz__chips" aria-labelledby="quiz-interests">
          {interests.map((interest) => (
            <li key={interest} className="chip">
              {INTEREST_LABELS[interest]}
            </li>
          ))}
        </ul>
      </div>

      <div className="screen__actions">
        <Button size="lg" onClick={buildHistory}>
          Build my history
        </Button>
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button variant="ghost" onClick={onRetake}>
          Retake the quiz
        </Button>
      </div>

      <SorterLine />
    </section>
  );
}

function isTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * One quiet line about the model downloading in the background. The visible
 * percentage is not announced; assistive technology hears only the three
 * status changes.
 */
function SorterLine() {
  const snapshot = useSorter();
  const { status, progress } = snapshot;
  // Small files finish before the model file starts, so a "100%" can appear early;
  // show the percentage only while a download is visibly under way.
  const percent =
    progress.total > 0 && progress.fraction < 1 ? Math.round(progress.fraction * 100) : null;

  let text: string;
  let announce: string;
  switch (status) {
    case "ready":
      text = "The sorter is ready.";
      announce = "The sorter is ready.";
      break;
    case "error":
      text = "The sorter will try again later.";
      announce = "The sorter could not load yet. It will try again later.";
      break;
    case "loading":
      text = percent === null ? "Preparing the sorter…" : `Preparing the sorter… ${percent}%`;
      announce = "Preparing the sorter in the background.";
      break;
    default:
      text = "";
      announce = "";
  }

  if (!text) return null;

  return (
    <div className="sorter-line" data-status={status}>
      <span className="sorter-line__dot" aria-hidden="true" />
      <span className="sorter-line__text">{text}</span>
      <span className="sorter-line__track" aria-hidden="true">
        <span
          className="sorter-line__fill"
          style={{ width: `${status === "ready" ? 100 : (percent ?? 0)}%` }}
        />
      </span>
      <span className="visually-hidden" role="status">
        {announce}
      </span>
    </div>
  );
}
