/**
 * Precomputed library embeddings written by scripts/precompute-embeddings.mjs
 * to src/generated/library-embeddings.json. The file is gitignored and may be
 * missing, so it is resolved through a glob that matches nothing then. It is
 * emitted as a static asset (not a script) and fetched only when the switch is
 * flipped, so its size never counts against the JavaScript budget.
 */
export interface LibraryEmbeddings {
  model: string;
  dim: number;
  vectors: Record<string, number[]>;
}

const urls = import.meta.glob<string>("../generated/library-embeddings.json", {
  query: "?url",
  import: "default",
});

let cached: Promise<LibraryEmbeddings | null> | null = null;

function isLibraryEmbeddings(value: unknown): value is LibraryEmbeddings {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.model === "string" &&
    typeof record.dim === "number" &&
    typeof record.vectors === "object" &&
    record.vectors !== null
  );
}

async function fetchEmbeddings(): Promise<LibraryEmbeddings | null> {
  const loader = Object.values(urls)[0];
  if (!loader) return null;
  try {
    const url = await loader();
    const response = await fetch(url);
    if (!response.ok) return null;
    const data: unknown = await response.json();
    return isLibraryEmbeddings(data) ? data : null;
  } catch {
    return null;
  }
}

/** The precomputed vectors, fetched once; null when the file is missing or unreadable. */
export function loadLibraryEmbeddings(): Promise<LibraryEmbeddings | null> {
  if (!cached) cached = fetchEmbeddings();
  return cached;
}
