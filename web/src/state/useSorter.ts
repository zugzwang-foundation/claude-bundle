import { useSyncExternalStore } from "react";
import { type SorterSnapshot, sorter } from "../sorter/client";

/** The sorter's status, progress and timings, live. */
export function useSorter(): SorterSnapshot {
  return useSyncExternalStore(sorter.subscribe, sorter.getSnapshot, sorter.getSnapshot);
}
