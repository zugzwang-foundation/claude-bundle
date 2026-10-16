/**
 * The published exam runs: one JSON file per run under scoreboard/runs/ at the
 * repository root, written by the Python pipeline (bundle_pipeline/scoreboard.py).
 * Contract: {run_id, label, date, exam_hash, base_model, sorters: [{id, name,
 * ...METRIC_KEYS}], notes}. Vite resolves the glob at build time, so the tech
 * view also works when no run has been published yet.
 */

export const METRIC_KEYS = [
  "accuracy",
  "macro_f1",
  "none_precision",
  "none_recall",
  "ece",
  "brier",
  "file_precision",
  "file_coverage",
  "suggest_precision",
  "suggest_coverage",
  "latency_ms_per_decision",
  "size_mb",
] as const;

export type MetricKey = (typeof METRIC_KEYS)[number];

export type MetricUnit = "percent" | "score" | "ms" | "mb";

export interface MetricInfo {
  key: MetricKey;
  label: string;
  /** A one-line explanation for the row header's title attribute. */
  hint: string;
  unit: MetricUnit;
  /** True when a larger value is better, false when smaller is better. */
  higherIsBetter: boolean;
}

export const METRICS: readonly MetricInfo[] = [
  {
    key: "accuracy",
    label: "Accuracy",
    hint: "Share of exam chats given the right answer: the right bundle, loose, or none.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "macro_f1",
    label: "Macro F1",
    hint: "F1 averaged over the classes bundle, loose and none, so rare classes count equally.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "none_precision",
    label: "Precision for none",
    hint: "When the sorter said none, how often it was right.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "none_recall",
    label: "Recall for none",
    hint: "Of the chats that belonged nowhere, how many the sorter left alone.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "ece",
    label: "Calibration error (ECE)",
    hint: "How far the percentages are from the truth; 0 is honest.",
    unit: "score",
    higherIsBetter: false,
  },
  {
    key: "brier",
    label: "Brier score",
    hint: "Mean squared error of the probabilities; 0 is perfect.",
    unit: "score",
    higherIsBetter: false,
  },
  {
    key: "file_precision",
    label: "Precision when filing",
    hint: "Above the file cut-off, how often the chosen bundle was right. Target 95%.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "file_coverage",
    label: "Coverage when filing",
    hint: "Share of chats confident enough to file without asking.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "suggest_precision",
    label: "Precision when suggesting",
    hint: "Above the suggest cut-off, how often the suggestion was right. Target 80%.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "suggest_coverage",
    label: "Coverage when suggesting",
    hint: "Share of chats that got at least a suggestion.",
    unit: "percent",
    higherIsBetter: true,
  },
  {
    key: "latency_ms_per_decision",
    label: "Latency per decision",
    hint: "Milliseconds per decision on the exam machine.",
    unit: "ms",
    higherIsBetter: false,
  },
  {
    key: "size_mb",
    label: "Size",
    hint: "Model files in megabytes.",
    unit: "mb",
    higherIsBetter: false,
  },
];

export interface ScoreboardSorter {
  id: string;
  name: string;
  metrics: Partial<Record<MetricKey, number>>;
}

export interface ScoreboardRun {
  runId: string;
  label: string;
  date: string;
  examHash: string;
  baseModel: string;
  sorters: ScoreboardSorter[];
  notes: string[];
  /** The glob key the run was read from, for stable React keys and sorting ties. */
  file: string;
}

export type RunModules = Record<string, unknown>;

const modules: RunModules = import.meta.glob("../../../scoreboard/runs/*.json", {
  eager: true,
  import: "default",
});

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function parseSorter(value: unknown): ScoreboardSorter | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  const id = asString(record.id);
  if (!id) return null;
  const metrics: Partial<Record<MetricKey, number>> = {};
  for (const key of METRIC_KEYS) {
    const n = asNumber(record[key]);
    if (n !== undefined) metrics[key] = n;
  }
  return { id, name: asString(record.name, id), metrics };
}

/** A run file as the pipeline writes it; null when the shape is not recognisable. */
export function parseRun(file: string, value: unknown): ScoreboardRun | null {
  if (typeof value !== "object" || value === null) return null;
  const record = value as Record<string, unknown>;
  const runId = asString(record.run_id);
  if (!runId || !Array.isArray(record.sorters)) return null;
  const sorters = record.sorters.map(parseSorter).filter((s): s is ScoreboardSorter => s !== null);
  const notes = Array.isArray(record.notes)
    ? record.notes.filter((n): n is string => typeof n === "string")
    : [];
  return {
    runId,
    label: asString(record.label, "unlabelled"),
    date: asString(record.date),
    examHash: asString(record.exam_hash),
    baseModel: asString(record.base_model),
    sorters,
    notes,
    file,
  };
}

/** Newest first: by date, then run id, then file name. */
export function sortRuns(runs: readonly ScoreboardRun[]): ScoreboardRun[] {
  return runs.slice().sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    if (a.runId !== b.runId) return a.runId < b.runId ? 1 : -1;
    return a.file < b.file ? 1 : a.file > b.file ? -1 : 0;
  });
}

/** Every recognisable run, newest first. */
export function loadRuns(source: RunModules = modules): ScoreboardRun[] {
  const runs: ScoreboardRun[] = [];
  for (const [file, value] of Object.entries(source)) {
    const run = parseRun(file, value);
    if (run) runs.push(run);
  }
  return sortRuns(runs);
}

/** The newest published run, or null when none exists. */
export function getLatestRun(source: RunModules = modules): ScoreboardRun | null {
  return loadRuns(source)[0] ?? null;
}

/** The id of the sorter with the best value for a metric; null when fewer than two have it. */
export function bestSorter(run: ScoreboardRun, metric: MetricInfo): string | null {
  let best: { id: string; value: number } | null = null;
  let seen = 0;
  for (const sorter of run.sorters) {
    const value = sorter.metrics[metric.key];
    if (value === undefined) continue;
    seen += 1;
    const better =
      best === null || (metric.higherIsBetter ? value > best.value : value < best.value);
    if (better) best = { id: sorter.id, value };
  }
  return seen >= 2 && best ? best.id : null;
}

export function formatMetric(unit: MetricUnit, value: number | undefined): string {
  if (value === undefined) return "—";
  switch (unit) {
    case "percent":
      return `${(value * 100).toFixed(1)}%`;
    case "score":
      return value.toFixed(3);
    case "ms":
      return `${value.toFixed(1)} ms`;
    case "mb":
      return `${value.toFixed(1)} MB`;
    default:
      return String(value);
  }
}

/** The first and last few characters of a hash, for display. */
export function shortHash(hash: string): string {
  if (hash.length <= 12) return hash;
  return `${hash.slice(0, 6)}…${hash.slice(-4)}`;
}
