import { BUDGETS } from "../config";
import calibration from "../sorter/calibration.json";
import manifest from "../sorter/model-manifest.json";
import { useFlow } from "../state/flow";
import { useSorter } from "../state/useSorter";
import { Panel } from "./Panel";

export function mean(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  let sum = 0;
  for (const v of values) sum += v;
  return sum / values.length;
}

export function median(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const hi = sorted[mid] ?? 0;
  if (sorted.length % 2 === 1) return hi;
  return ((sorted[mid - 1] ?? 0) + hi) / 2;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1) return `${ms.toFixed(2)} ms`;
  if (ms < 100) return `${ms.toFixed(1)} ms`;
  if (ms < 10_000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function formatMb(bytes: number): string {
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

const DEVICE_LABEL = { webgpu: "WebGPU (graphics card)", wasm: "WASM (CPU)" } as const;

/** Compressed bytes of every script this page has fetched so far, from the Resource Timing API. */
function scriptKilobytes(): number | null {
  if (typeof performance === "undefined" || typeof performance.getEntriesByType !== "function") {
    return null;
  }
  let bytes = 0;
  let seen = false;
  for (const entry of performance.getEntriesByType("resource")) {
    const timing = entry as PerformanceResourceTiming;
    if (/\.[mc]?js(\?|$)/.test(timing.name) && timing.transferSize > 0) {
      bytes += timing.transferSize;
      seen = true;
    }
  }
  return seen ? bytes / 1024 : null;
}

/** The model, the device it runs on, and the latencies measured on this visit. */
export function ModelInfo() {
  const sorter = useSorter();
  const { state } = useFlow();
  const result = state.bundling;
  const decisionTimes = result ? result.steps.map((s) => s.ms) : [];
  const med = median(decisionTimes);
  const avg = mean(decisionTimes);
  const max = decisionTimes.length > 0 ? Math.max(...decisionTimes) : null;
  const scriptKb = scriptKilobytes();
  const progress = Math.round(sorter.progress.fraction * 100);

  let statusText: string;
  switch (sorter.status) {
    case "idle":
      statusText = "Waiting. The download starts with the quiz.";
      break;
    case "loading":
      statusText = `Downloading and warming up · ${progress}%${
        sorter.progress.file ? ` · ${sorter.progress.file}` : ""
      }`;
      break;
    case "ready":
      statusText = "Ready";
      break;
    default:
      statusText = `Failed: ${sorter.error ?? "unknown error"}`;
  }

  // Read out to assistive technology: the four coarse states only, never the per-file progress.
  const announce =
    sorter.status === "idle"
      ? "Sorter waiting."
      : sorter.status === "loading"
        ? "Sorter downloading."
        : sorter.status === "ready"
          ? "Sorter ready."
          : "Sorter failed.";

  const summary =
    sorter.status === "ready" && sorter.ready
      ? `${DEVICE_LABEL[sorter.ready.device]} · ${formatMb(sorter.ready.sizeBytes)}`
      : sorter.status === "loading"
        ? `${progress}%`
        : undefined;

  return (
    <Panel id="tech-model" title="Model and latency" summary={summary} wide={result !== null}>
      <dl className="facts">
        <dt>Model</dt>
        <dd>
          {manifest.name}
          <span className="facts__hint">
            {" "}
            · {manifest.id} · {manifest.dtype} ·{" "}
            {manifest.source === "local" ? "served from this site" : "from the Hugging Face hub"}
          </span>
        </dd>

        <dt>Status</dt>
        <dd>
          <span className="visually-hidden" role="status">
            {announce}
          </span>
          {statusText}
          {sorter.status === "loading" && (
            <progress
              className="facts__progress"
              value={sorter.progress.fraction}
              max={1}
              aria-label="Model download"
            />
          )}
        </dd>

        <dt>Device</dt>
        <dd>
          {sorter.ready ? DEVICE_LABEL[sorter.ready.device] : "—"}
          {sorter.ready?.device === "wasm" && (
            <span className="facts__hint"> · WebGPU not available here, so the CPU fallback</span>
          )}
        </dd>

        <dt>Download</dt>
        <dd>
          {sorter.ready ? formatMb(sorter.ready.sizeBytes) : "—"}
          <span className="facts__hint"> · budget {BUDGETS.modelMb} MB</span>
          {sorter.ready && (
            <span className="facts__verdict">
              {sorter.ready.sizeBytes / 1_048_576 <= BUDGETS.modelMb
                ? " · within budget"
                : " · over budget"}
            </span>
          )}
        </dd>

        <dt>Load time</dt>
        <dd>
          {sorter.ready ? formatMs(sorter.ready.loadMs) : "—"}
          <span className="facts__hint"> · download, compile and first run</span>
        </dd>

        <dt>Embedding</dt>
        <dd>
          {formatMs(sorter.lastEmbedMs)}
          <span className="facts__hint"> · latest call to the worker, all texts in one batch</span>
          {result && result.embedMs > 0 && (
            <span className="facts__hint"> · {formatMs(result.embedMs)} during the sort</span>
          )}
        </dd>

        <dt>Per decision</dt>
        <dd>
          {decisionTimes.length === 0 ? (
            <>
              — <span className="facts__hint">· measured when you flip the switch</span>
            </>
          ) : (
            <>
              median {formatMs(med)}, mean {formatMs(avg)}, max {formatMs(max)}
              <span className="facts__hint">
                {" "}
                · {decisionTimes.length} decisions, scoring and rules only
              </span>
            </>
          )}
          <span className="facts__hint"> · budget {BUDGETS.decisionMs} ms</span>
          {med !== null && (
            <span className="facts__verdict">
              {med <= BUDGETS.decisionMs ? " · within budget" : " · over budget"}
            </span>
          )}
        </dd>

        <dt>JavaScript</dt>
        <dd>
          budget {BUDGETS.jsGzipKb} KB gzipped before the model
          {scriptKb !== null && (
            <span className="facts__hint">
              {" "}
              · this visit fetched {Math.round(scriptKb)} KB of scripts (compressed)
              {import.meta.env.DEV ? ", unbundled dev server, not comparable" : ""}
            </span>
          )}
        </dd>

        <dt>Calibration</dt>
        <dd>
          temperature {calibration.temperature}, none {calibration.noneScore}, file ≥{" "}
          {calibration.fileCutoff}, suggest ≥ {calibration.suggestCutoff}
          <span className="facts__hint"> · {calibration.source}</span>
        </dd>
      </dl>
    </Panel>
  );
}
