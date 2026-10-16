/** What a chat can be filed against: an existing bundle or a single loose chat. */
export type CandidateKind = "bundle" | "loose";

export interface Candidate {
  id: string;
  kind: CandidateKind;
  /** A bundle's display name. */
  label?: string;
  /** A bundle's member texts; its vector is the normalised mean of their vectors. */
  examples?: string[];
  /** A loose chat's own text; its vector is its own embedding. */
  text?: string;
}

export type Action = "file" | "suggest" | "leave";

export interface Decision {
  /** One probability per candidate id plus "none"; they sum to 1. */
  probabilities: Record<string, number>;
  action: Action;
  /** The top candidate's id, or null when the action is "leave". */
  target: string | null;
}

/** Thresholds and softmax settings shared with the Python pipeline (src/sorter/calibration.json). */
export interface Calibration {
  model: string;
  temperature: number;
  noneScore: number;
  fileCutoff: number;
  suggestCutoff: number;
  source: string;
}

/** Any numeric vector: a Float32Array from the model or a number[] from JSON. */
export type Vector = ArrayLike<number>;

export interface ScoredCandidate {
  id: string;
  vector: Vector;
}
