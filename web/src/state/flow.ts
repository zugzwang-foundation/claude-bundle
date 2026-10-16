import {
  createContext,
  createElement,
  type Dispatch,
  type ReactNode,
  useContext,
  useMemo,
  useReducer,
} from "react";
import type { HistoryChat } from "../content/types";
import type { BundlingResult } from "../sorter/bundler";
import { nextStep, previousStep, STEPS, type Step } from "./steps";

export type { HistoryChat } from "../content/types";
export { STEP_LABELS, STEPS, type Step } from "./steps";

export type Theme = "light" | "dark";

export interface Personality {
  /** An original type name, e.g. "Weekend Explorer". */
  type: string;
  /** Three to five interest ids from the library. */
  interests: string[];
}

export interface ChallengeState {
  /** The id of the visitor's own chat they must find. */
  targetId: string | null;
  /** Time to find it by scrolling and searching. */
  beforeMs: number | null;
  /** Time to find it once bundled. */
  afterMs: number | null;
  /** True when the visitor gave up instead of finding it (set by the challenge screen). */
  gaveUp?: boolean;
}

export interface FlowState {
  step: Step;
  /** questionId -> optionId */
  quizAnswers: Record<string, string>;
  personality: Personality | null;
  /** Library chats in the visitor's history, dated. */
  history: HistoryChat[];
  /** Chats the visitor asked during the demo. */
  myChats: HistoryChat[];
  challenge: ChallengeState;
  bundling: BundlingResult | null;
  theme: Theme;
  techView: boolean;
  /** Seeds library assembly so a visit is reproducible. */
  seed: number;
  /** The fixed "today" (ISO 8601) the history is dated against; set once when the history is assembled. */
  now?: string;
}

export type FlowAction =
  | { type: "go"; step: Step }
  | { type: "next" }
  | { type: "back" }
  | { type: "answer"; questionId: string; optionId: string }
  | { type: "setPersonality"; personality: Personality }
  | { type: "setHistory"; chats: HistoryChat[] }
  | { type: "appendHistory"; chats: HistoryChat[] }
  | { type: "addMyChat"; chat: HistoryChat }
  | { type: "setChallengeTarget"; targetId: string | null }
  | { type: "setChallengeTime"; which: "before" | "after"; ms: number }
  | { type: "setBundling"; result: BundlingResult | null }
  | { type: "setTheme"; theme: Theme }
  | { type: "toggleTheme" }
  | { type: "setTechView"; on: boolean }
  | { type: "toggleTechView" }
  | { type: "reset" }
  | { type: "setNow"; now: string }
  | { type: "setChallengeGaveUp"; gaveUp: boolean };

export interface FlowInit {
  theme?: Theme;
  techView?: boolean;
  seed?: number;
}

export function initialState(init: FlowInit = {}): FlowState {
  return {
    step: "welcome",
    quizAnswers: {},
    personality: null,
    history: [],
    myChats: [],
    challenge: { targetId: null, beforeMs: null, afterMs: null },
    bundling: null,
    theme: init.theme ?? "light",
    techView: init.techView ?? false,
    seed: init.seed ?? 1,
  };
}

export function flowReducer(state: FlowState, action: FlowAction): FlowState {
  switch (action.type) {
    case "go":
      return STEPS.includes(action.step) ? { ...state, step: action.step } : state;
    case "next":
      return { ...state, step: nextStep(state.step) };
    case "back":
      return { ...state, step: previousStep(state.step) };
    case "answer":
      return {
        ...state,
        quizAnswers: { ...state.quizAnswers, [action.questionId]: action.optionId },
      };
    case "setPersonality":
      return { ...state, personality: action.personality };
    case "setHistory":
      return { ...state, history: action.chats };
    case "appendHistory":
      return { ...state, history: [...state.history, ...action.chats] };
    case "addMyChat":
      return { ...state, myChats: [...state.myChats, action.chat] };
    case "setChallengeTarget":
      return { ...state, challenge: { ...state.challenge, targetId: action.targetId } };
    case "setChallengeTime":
      return action.which === "before"
        ? { ...state, challenge: { ...state.challenge, beforeMs: action.ms } }
        : { ...state, challenge: { ...state.challenge, afterMs: action.ms } };
    case "setBundling":
      return { ...state, bundling: action.result };
    case "setTheme":
      return { ...state, theme: action.theme };
    case "toggleTheme":
      return { ...state, theme: state.theme === "dark" ? "light" : "dark" };
    case "setTechView":
      return { ...state, techView: action.on };
    case "toggleTechView":
      return { ...state, techView: !state.techView };
    case "reset":
      return initialState({ theme: state.theme, techView: state.techView, seed: state.seed + 1 });
    case "setChallengeGaveUp":
      return { ...state, challenge: { ...state.challenge, gaveUp: action.gaveUp } };
    case "setNow":
      return { ...state, now: action.now };
    default:
      return state;
  }
}

export interface FlowContextValue {
  state: FlowState;
  dispatch: Dispatch<FlowAction>;
}

const FlowContext = createContext<FlowContextValue | null>(null);

function systemTheme(): Theme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function randomSeed(): number {
  return Math.floor(Math.random() * 0x7fffffff);
}

export function FlowProvider({ children, init }: { children: ReactNode; init?: FlowInit }) {
  const [state, dispatch] = useReducer(flowReducer, init, (given) =>
    initialState({
      theme: given?.theme ?? systemTheme(),
      techView: given?.techView ?? false,
      seed: given?.seed ?? randomSeed(),
    }),
  );
  const value = useMemo(() => ({ state, dispatch }), [state]);
  return createElement(FlowContext.Provider, { value }, children);
}

export function useFlow(): FlowContextValue {
  const value = useContext(FlowContext);
  if (!value) throw new Error("useFlow must be used inside FlowProvider");
  return value;
}
