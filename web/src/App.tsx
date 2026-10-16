import { lazy, Suspense, useEffect, useRef } from "react";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { Challenge } from "./screens/Challenge";
import { Chat } from "./screens/Chat";
import { Continue } from "./screens/Continue";
import { History } from "./screens/History";
import { MonthsPass } from "./screens/MonthsPass";
import { Quiz } from "./screens/Quiz";
import { Reveal } from "./screens/Reveal";
import { Welcome } from "./screens/Welcome";
import { sorter } from "./sorter/client";
import { FlowProvider, type Step, type Theme, useFlow } from "./state/flow";
import { useSorter } from "./state/useSorter";
import { publishBundleStats } from "./testing";

/** The tech view is its own chunk: visitors who never flip that switch never download it. */
const TechPanel = lazy(() =>
  import("./tech/TechPanel").then((module) => ({ default: module.TechPanel })),
);

const THEME_COLOR: Record<Theme, string> = { light: "#F2F4F7", dark: "#0F131A" };

function Screen({ step }: { step: Step }) {
  switch (step) {
    case "welcome":
      return <Welcome />;
    case "quiz":
      return <Quiz />;
    case "history":
      return <History />;
    case "chat":
      return <Chat />;
    case "months":
      return <MonthsPass />;
    case "challenge":
      return <Challenge />;
    case "reveal":
      return <Reveal />;
    case "continue":
      return <Continue />;
    default:
      return <Welcome />;
  }
}

function Shell() {
  const { state } = useFlow();
  const sorterState = useSorter();
  const lastStep = useRef(state.step);

  // Each new step hands focus to its heading, so keyboard and screen-reader users land on the
  // new content instead of on <body>; the page scrolls back to the top at the same time.
  useEffect(() => {
    if (lastStep.current === state.step) return;
    lastStep.current = state.step;
    window.scrollTo({ top: 0 });
    const heading = document.querySelector<HTMLHeadingElement>("#main h1");
    if (!heading) return;
    if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }, [state.step]);

  useEffect(() => {
    document.documentElement.dataset.theme = state.theme;
    for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
      meta.content = THEME_COLOR[state.theme];
    }
  }, [state.theme]);

  // The model starts downloading while the visitor answers the quiz.
  useEffect(() => {
    if (state.step === "quiz") sorter.load().catch(() => undefined);
  }, [state.step]);

  // Only with ?test in the URL: the Playwright run reads the measured latencies from the window.
  useEffect(() => {
    publishBundleStats(state.bundling, sorterState.ready);
  }, [state.bundling, sorterState.ready]);

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main" className="app__main" tabIndex={-1}>
        <Screen step={state.step} />
        {state.techView && (
          <Suspense
            fallback={
              <p className="tech-loading" aria-live="polite">
                Loading the tech view…
              </p>
            }
          >
            <TechPanel />
          </Suspense>
        )}
      </main>
      <Footer />
    </div>
  );
}

export function App() {
  return (
    <FlowProvider>
      <Shell />
    </FlowProvider>
  );
}
