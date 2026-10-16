import type { BundlingResult } from "./sorter/bundler";
import type { ReadyInfo } from "./sorter/messages";

/**
 * Hooks for the Playwright run, on only when the page is opened with `?test`:
 * the challenge heading carries its target's title, and the window gets the
 * sorter's measurements once the chats are bundled. Visitors never hit this path.
 */
export const TEST_MODE: boolean =
  typeof window !== "undefined" && new URLSearchParams(window.location.search).has("test");

export interface BundleStats {
  count: number;
  medianMs: number;
  meanMs: number;
  p95Ms: number;
  maxMs: number;
  /** Time the worker spent embedding during the sort, in ms. */
  embedMs: number;
  /** Time spent scoring and applying the rules during the sort, in ms. */
  decisionMs: number;
  bundles: number;
  loose: number;
  device: string | null;
  model: string | null;
  /** Bytes the model and tokenizer files add up to, as the worker saw them. */
  sizeBytes: number | null;
  loadMs: number | null;
}

declare global {
  interface Window {
    __bundleStats?: BundleStats;
  }
}

export function bundleStats(result: BundlingResult, ready: ReadyInfo | null): BundleStats {
  const times = result.steps.map((step) => step.ms).sort((a, b) => a - b);
  const count = times.length;
  const sum = times.reduce((acc, t) => acc + t, 0);
  const mid = Math.floor(count / 2);
  const median =
    count === 0
      ? 0
      : count % 2 === 1
        ? (times[mid] ?? 0)
        : ((times[mid - 1] ?? 0) + (times[mid] ?? 0)) / 2;
  return {
    count,
    medianMs: median,
    meanMs: count ? sum / count : 0,
    p95Ms: times[Math.min(count - 1, Math.floor(count * 0.95))] ?? 0,
    maxMs: times[count - 1] ?? 0,
    embedMs: result.embedMs,
    decisionMs: result.decisionMs,
    bundles: result.bundles.length,
    loose: result.loose.length,
    device: ready?.device ?? null,
    model: ready?.model ?? null,
    sizeBytes: ready?.sizeBytes ?? null,
    loadMs: ready?.loadMs ?? null,
  };
}

/** Publish the sort's measurements for the test runner. A no-op outside test mode. */
export function publishBundleStats(result: BundlingResult | null, ready: ReadyInfo | null): void {
  if (!TEST_MODE || !result) return;
  window.__bundleStats = bundleStats(result, ready);
}
