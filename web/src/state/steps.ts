/** The eight steps of the story, in order. */
export const STEPS = [
  "welcome",
  "quiz",
  "history",
  "chat",
  "months",
  "challenge",
  "reveal",
  "continue",
] as const;

export type Step = (typeof STEPS)[number];

export const STEP_LABELS: Record<Step, string> = {
  welcome: "Welcome",
  quiz: "Quiz",
  history: "History",
  chat: "Chat",
  months: "Months pass",
  challenge: "Challenge",
  reveal: "Reveal",
  continue: "Continue",
};

export function stepIndex(step: Step): number {
  return STEPS.indexOf(step);
}

export function nextStep(step: Step): Step {
  return STEPS[Math.min(stepIndex(step) + 1, STEPS.length - 1)] ?? step;
}

export function previousStep(step: Step): Step {
  return STEPS[Math.max(stepIndex(step) - 1, 0)] ?? step;
}
