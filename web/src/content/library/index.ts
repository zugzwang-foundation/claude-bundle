import type { LibraryInterest } from "../types";

/**
 * Every interest file in this folder, except the schema. Vite resolves the glob
 * at build time, so the app also works when no interest files exist yet.
 */
const modules = import.meta.glob<LibraryInterest>(["./*.json", "!./library.schema.json"], {
  eager: true,
  import: "default",
});

function isLibraryInterest(value: unknown): value is LibraryInterest {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.interest === "string" &&
    typeof record.label === "string" &&
    Array.isArray(record.threads) &&
    Array.isArray(record.oneOffs)
  );
}

let cache: LibraryInterest[] | null = null;

/** All interests, sorted by file name. Empty when no interest files exist. */
export function getLibrary(): LibraryInterest[] {
  if (cache === null) {
    cache = Object.keys(modules)
      .sort()
      .map((key) => modules[key])
      .filter(isLibraryInterest);
  }
  return cache;
}

/** The ids of every interest in the library. */
export function getInterestIds(library: LibraryInterest[] = getLibrary()): string[] {
  return library.map((entry) => entry.interest);
}
