import { useMemo, useSyncExternalStore } from "react";

/** True while the media query matches; false during server rendering. */
export function useMediaQuery(query: string): boolean {
  const subscribe = useMemo(
    () => (onChange: () => void) => {
      if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
        return () => undefined;
      }
      const media = window.matchMedia(query);
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    },
    [query],
  );
  const getSnapshot = () =>
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(query).matches;
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}

export function usePrefersReducedMotion(): boolean {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
