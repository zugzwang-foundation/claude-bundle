import { useState } from "react";
import { APP_NAME } from "../config";
import type { HistoryChat } from "../content/types";
import calibration from "../sorter/calibration.json";
import type { Action } from "../sorter/types";
import { useFlow } from "../state/flow";
import { Panel } from "./Panel";

const ACTION_LABEL: Record<Action, string> = {
  file: "Filed",
  suggest: "Suggested",
  leave: "Left loose",
};

/** How many rows show before "Show all". */
const PREVIEW_ROWS = 24;

function percent(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

function formatMs(ms: number): string {
  return `${ms < 1 ? ms.toFixed(2) : ms.toFixed(1)} ms`;
}

/**
 * One bar per chat after the reveal: the probability of its best match,
 * coloured by the action the three rules chose, with the two cut-offs marked
 * on every track. Before the reveal it says what will appear and at which
 * cut-offs.
 */
export function ProbabilityBars() {
  const { state } = useFlow();
  const [showAll, setShowAll] = useState(false);
  const result = state.bundling;
  const fileCut = calibration.fileCutoff;
  const suggestCut = calibration.suggestCutoff;

  if (!result) {
    const waiting = state.step === "reveal" || state.step === "continue";
    return (
      <Panel id="tech-bars" title="Probability bars">
        <p className="tech__note" aria-live="polite">
          {waiting
            ? `Flip “${APP_NAME} my chats” and every decision lands here, one bar per chat.`
            : "Bars appear after the reveal, one per chat."}
        </p>
        <p className="tech__muted">
          Each bar is the probability of the chat's best match among the bundles and loose chats it
          has at that moment. The rules: file at {percent(fileCut)} or more, suggest at{" "}
          {percent(suggestCut)} or more, otherwise leave it loose.
        </p>
      </Panel>
    );
  }

  const chats = new Map<string, HistoryChat>();
  for (const chat of state.history) chats.set(chat.id, chat);
  for (const chat of state.myChats) chats.set(chat.id, chat);
  const bundleName = new Map(result.bundles.map((b) => [b.id, b.name] as const));

  const counts: Record<Action, number> = { file: 0, suggest: 0, leave: 0 };
  for (const step of result.steps) counts[step.action] += 1;
  const total = result.steps.length;
  const rows = showAll ? result.steps : result.steps.slice(0, PREVIEW_ROWS);
  const hidden = total - rows.length;

  return (
    <Panel id="tech-bars" title="Probability bars" summary={`${total} decisions`} wide>
      <p className="tech__note" aria-live="polite">
        {total} chats in date order: {counts.file} filed, {counts.suggest} suggested, {counts.leave}{" "}
        left loose.
      </p>
      <ul className="bars__legend" aria-label="Colour key">
        <li>
          <span className="swatch swatch--file" aria-hidden="true" />
          Filed (≥ {percent(fileCut)})
        </li>
        <li>
          <span className="swatch swatch--suggest" aria-hidden="true" />
          Suggested (≥ {percent(suggestCut)})
        </li>
        <li>
          <span className="swatch swatch--leave" aria-hidden="true" />
          Left loose
        </li>
        <li>
          <span className="swatch swatch--cut" aria-hidden="true" />
          Cut-offs
        </li>
      </ul>
      <ol className="bars__list">
        {rows.map((step) => {
          const chat = chats.get(step.chatId);
          const placement = result.placements[step.chatId];
          const action = placement?.action ?? step.action;
          const p = placement?.probability ?? step.probability;
          const target = placement?.bundleId ? bundleName.get(placement.bundleId) : undefined;
          return (
            <li key={step.chatId} className="bar" data-action={action}>
              <span className="bar__title">
                {chat?.title ?? step.chatId}
                {chat?.mine && <span className="bar__mine">yours</span>}
              </span>
              <span className="bar__value">
                <span className="visually-hidden">best match </span>
                {percent(p)}
              </span>
              <div className="bar__track" aria-hidden="true">
                <div className="bar__fill" style={{ width: `${Math.min(100, p * 100)}%` }} />
                <span className="bar__cut" style={{ left: `${suggestCut * 100}%` }} />
                <span className="bar__cut" style={{ left: `${fileCut * 100}%` }} />
              </div>
              <span className="bar__meta">
                {ACTION_LABEL[action]}
                {target ? ` · ${target}` : ""}
                {` · ${formatMs(step.ms)}`}
              </span>
            </li>
          );
        })}
      </ol>
      {total > PREVIEW_ROWS && (
        <button
          type="button"
          className="tech__more"
          aria-expanded={showAll}
          onClick={() => setShowAll((v) => !v)}
        >
          {showAll ? `Show the first ${PREVIEW_ROWS}` : `Show all ${total} (${hidden} more)`}
        </button>
      )}
    </Panel>
  );
}
