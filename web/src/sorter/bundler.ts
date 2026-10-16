import type { HistoryChat } from "../content/types";
import { decide } from "./rules";
import { meanVector, probabilities } from "./scoring";
import { chatText } from "./text";
import type { Action, Calibration, ScoredCandidate, Vector } from "./types";

export interface Bundle {
  id: string;
  /** For now, the title of the oldest chat in the bundle. */
  name: string;
  chatIds: string[];
  vector: Float32Array;
}

export interface Placement {
  chatId: string;
  bundleId: string | null;
  /** The probability of the chosen target, or of the best candidate when left loose. */
  probability: number;
  action: Action;
  suggested: boolean;
}

/** One decision, in processing order, for replaying the sort on screen. */
export interface BundleStep {
  chatId: string;
  action: Action;
  targetId: string | null;
  /** Set when this decision created a new bundle out of two loose chats. */
  createdBundleId: string | null;
  probability: number;
  probabilities: Record<string, number>;
  /** Milliseconds spent on this decision (scoring and rules, not embedding). */
  ms: number;
}

export interface BundlingResult {
  bundles: Bundle[];
  loose: string[];
  placements: Record<string, Placement>;
  steps: BundleStep[];
  /** Milliseconds spent embedding the chats that had no precomputed vector. */
  embedMs: number;
  /** Total milliseconds for all decisions. */
  decisionMs: number;
}

export type Embed = (texts: string[]) => Promise<Float32Array[]>;

export interface BundleOptions {
  calibration: Calibration;
  embed: Embed;
  /** Vectors by library chat id. Chats the visitor asked themselves are always embedded live. */
  precomputed?: Record<string, Vector> | null;
  onStep?: (step: BundleStep, index: number, total: number) => void;
  /** A clock, for tests. Defaults to performance.now. */
  now?: () => number;
}

function byDate(a: HistoryChat, b: HistoryChat): number {
  return Date.parse(a.date) - Date.parse(b.date);
}

/**
 * Sort a history into bundles the way the pipeline would, one chat at a time
 * in date order. Each chat is decided against the current bundles and loose
 * chats: "file" and "suggest" place it (joining a bundle, or forming one with a
 * loose chat), "leave" keeps it loose.
 */
export async function bundleChats(
  chats: readonly HistoryChat[],
  options: BundleOptions,
): Promise<BundlingResult> {
  const now = options.now ?? (() => performance.now());
  const ordered = chats.slice().sort(byDate);

  // Vectors: precomputed where allowed, live for the rest.
  const vectors = new Map<string, Vector>();
  const toEmbed: HistoryChat[] = [];
  for (const chat of ordered) {
    const ready = chat.mine ? undefined : options.precomputed?.[chat.libraryId];
    if (ready) vectors.set(chat.id, ready);
    else toEmbed.push(chat);
  }
  const embedStart = now();
  if (toEmbed.length > 0) {
    const live = await options.embed(toEmbed.map((chat) => chatText(chat)));
    toEmbed.forEach((chat, i) => {
      const v = live[i];
      if (v) vectors.set(chat.id, v);
    });
  }
  const embedMs = now() - embedStart;

  const bundles: Bundle[] = [];
  const loose: string[] = [];
  const placements: Record<string, Placement> = {};
  const steps: BundleStep[] = [];
  let decisionMs = 0;

  const vectorOf = (chatId: string): Vector => vectors.get(chatId) ?? new Float32Array(0);

  for (const [index, chat] of ordered.entries()) {
    const t0 = now();
    const candidates: ScoredCandidate[] = [
      ...bundles.map((b) => ({ id: b.id, vector: b.vector })),
      ...loose.map((id) => ({ id, vector: vectorOf(id) })),
    ];
    const p = probabilities(vectorOf(chat.id), candidates, options.calibration);
    const decision = decide(p, options.calibration);
    let createdBundleId: string | null = null;
    let bundleId: string | null = null;
    let probability = 0;
    for (const [id, value] of Object.entries(p)) {
      if (id !== "none" && value > probability) probability = value;
    }

    if (decision.action === "leave" || decision.target === null) {
      loose.push(chat.id);
    } else {
      const target = decision.target;
      probability = p[target] ?? probability;
      const existing = bundles.find((b) => b.id === target);
      if (existing) {
        existing.chatIds.push(chat.id);
        existing.vector = meanVector(existing.chatIds.map(vectorOf));
        bundleId = existing.id;
      } else {
        // The target is a loose chat: the two form a new bundle named after the older one.
        const older = ordered.find((c) => c.id === target);
        const created: Bundle = {
          id: `bundle-${bundles.length + 1}`,
          name: older?.title ?? chat.title,
          chatIds: [target, chat.id],
          vector: meanVector([vectorOf(target), vectorOf(chat.id)]),
        };
        bundles.push(created);
        const at = loose.indexOf(target);
        if (at >= 0) loose.splice(at, 1);
        const previous = placements[target];
        if (previous) placements[target] = { ...previous, bundleId: created.id };
        bundleId = created.id;
        createdBundleId = created.id;
      }
    }

    placements[chat.id] = {
      chatId: chat.id,
      bundleId,
      probability,
      action: decision.action,
      suggested: decision.action === "suggest",
    };
    const ms = now() - t0;
    decisionMs += ms;
    const step: BundleStep = {
      chatId: chat.id,
      action: decision.action,
      targetId: decision.target,
      createdBundleId,
      probability,
      probabilities: p,
      ms,
    };
    steps.push(step);
    options.onStep?.(step, index, ordered.length);
  }

  return { bundles, loose, placements, steps, embedMs, decisionMs };
}
