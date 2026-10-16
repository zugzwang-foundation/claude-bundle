/** The product's name. This is the only place in the app code where it is written. */
export const APP_NAME = "Bundle";

/** Shown in the footer of every screen. */
export const FOOTER_TEXT =
  "An independent open-source project. Not affiliated with any AI company.";

/** Budgets from the relay (W5). They are measured and reported in README.md. */
export const JS_BUDGET_KB = 200;
export const MODEL_BUDGET_MB = 40;
export const DECISION_BUDGET_MS = 50;

export const BUDGETS = {
  jsGzipKb: JS_BUDGET_KB,
  modelMb: MODEL_BUDGET_MB,
  decisionMs: DECISION_BUDGET_MS,
} as const;
