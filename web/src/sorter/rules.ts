import { NONE_ID } from "./scoring";
import type { Calibration, Decision } from "./types";

/**
 * The three rules, identical to the Python pipeline:
 * top = argmax over the candidates (never "none");
 * file when p(top) >= fileCutoff, suggest when >= suggestCutoff, else leave;
 * the target is the top candidate unless the action is leave.
 */
export function decide(
  probabilities: Record<string, number>,
  calibration: Pick<Calibration, "fileCutoff" | "suggestCutoff">,
): Decision {
  let top: string | null = null;
  let pTop = Number.NEGATIVE_INFINITY;
  for (const [id, p] of Object.entries(probabilities)) {
    if (id === NONE_ID) continue;
    if (p > pTop) {
      pTop = p;
      top = id;
    }
  }
  if (top === null) return { probabilities, action: "leave", target: null };
  const action =
    pTop >= calibration.fileCutoff
      ? "file"
      : pTop >= calibration.suggestCutoff
        ? "suggest"
        : "leave";
  return { probabilities, action, target: action === "leave" ? null : top };
}

/** The top candidate's id and probability, ignoring "none"; null when there are no candidates. */
export function topCandidate(
  probabilities: Record<string, number>,
): { id: string; probability: number } | null {
  const decision = decide(probabilities, { fileCutoff: 2, suggestCutoff: 2 });
  if (decision.target !== null) return { id: decision.target, probability: 0 };
  let best: { id: string; probability: number } | null = null;
  for (const [id, p] of Object.entries(probabilities)) {
    if (id === NONE_ID) continue;
    if (!best || p > best.probability) best = { id, probability: p };
  }
  return best;
}
