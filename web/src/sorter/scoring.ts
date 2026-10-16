import type { Calibration, Candidate, ScoredCandidate, Vector } from "./types";

export const NONE_ID = "none";

export function dot(a: Vector, b: Vector): number {
  const n = Math.min(a.length, b.length);
  let sum = 0;
  for (let i = 0; i < n; i += 1) sum += (a[i] ?? 0) * (b[i] ?? 0);
  return sum;
}

export function norm(v: Vector): number {
  return Math.sqrt(dot(v, v));
}

/** The vector scaled to unit length; a zero vector stays zero. */
export function l2Normalize(v: Vector): Float32Array {
  const out = new Float32Array(v.length);
  const length = norm(v);
  if (length === 0) return out;
  for (let i = 0; i < v.length; i += 1) out[i] = (v[i] ?? 0) / length;
  return out;
}

/** Cosine similarity; 0 when either vector is zero. */
export function cosine(a: Vector, b: Vector): number {
  const na = norm(a);
  const nb = norm(b);
  if (na === 0 || nb === 0) return 0;
  return dot(a, b) / (na * nb);
}

/** The normalised mean of several vectors, as the Python pipeline computes a bundle's vector. */
export function meanVector(vectors: readonly Vector[]): Float32Array {
  const first = vectors[0];
  if (!first) return new Float32Array(0);
  const sum = new Float64Array(first.length);
  for (const v of vectors) {
    for (let i = 0; i < sum.length; i += 1) sum[i] = (sum[i] ?? 0) + (v[i] ?? 0);
  }
  for (let i = 0; i < sum.length; i += 1) sum[i] = (sum[i] ?? 0) / vectors.length;
  return l2Normalize(sum);
}

/** softmax(scores / temperature), numerically stable; an empty input stays empty. */
export function softmax(
  scores: Record<string, number>,
  temperature: number,
): Record<string, number> {
  const ids = Object.keys(scores);
  if (ids.length === 0) return {};
  const t = temperature > 0 ? temperature : 1e-9;
  let max = Number.NEGATIVE_INFINITY;
  for (const id of ids) max = Math.max(max, scores[id] ?? 0);
  const exps: Record<string, number> = {};
  let total = 0;
  for (const id of ids) {
    const e = Math.exp(((scores[id] ?? 0) - max) / t);
    exps[id] = e;
    total += e;
  }
  const out: Record<string, number> = {};
  for (const id of ids) out[id] = (exps[id] ?? 0) / total;
  return out;
}

/** Cosine of the query against each candidate vector, plus a constant score for "none". */
export function scoreVectors(
  query: Vector,
  candidates: readonly ScoredCandidate[],
  noneScore: number,
): Record<string, number> {
  const scores: Record<string, number> = {};
  for (const candidate of candidates) scores[candidate.id] = cosine(query, candidate.vector);
  scores[NONE_ID] = noneScore;
  return scores;
}

/** Probabilities over the candidates and "none": softmax(scores / temperature). */
export function probabilities(
  query: Vector,
  candidates: readonly ScoredCandidate[],
  calibration: Pick<Calibration, "temperature" | "noneScore">,
): Record<string, number> {
  return softmax(scoreVectors(query, candidates, calibration.noneScore), calibration.temperature);
}

/**
 * Turn text candidates into vectors: a bundle is the normalised mean of its
 * examples' vectors, a loose chat is its own. Candidates whose texts have no
 * vector are skipped.
 */
export function candidateVectors(
  candidates: readonly Candidate[],
  vectorOf: (text: string) => Vector | undefined,
): ScoredCandidate[] {
  const out: ScoredCandidate[] = [];
  for (const candidate of candidates) {
    if (candidate.kind === "bundle") {
      const vectors = (candidate.examples ?? [])
        .map(vectorOf)
        .filter((v): v is Vector => v !== undefined);
      if (vectors.length > 0) out.push({ id: candidate.id, vector: meanVector(vectors) });
    } else if (candidate.text !== undefined) {
      const vector = vectorOf(candidate.text);
      if (vector) out.push({ id: candidate.id, vector });
    }
  }
  return out;
}
