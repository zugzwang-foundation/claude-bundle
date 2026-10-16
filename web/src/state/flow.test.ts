import { describe, expect, it } from "vitest";
import { flowReducer, initialState, STEPS } from "./flow";

describe("flowReducer", () => {
  it("walks forward through every step and stops at the end", () => {
    let state = initialState();
    for (const step of STEPS) {
      expect(state.step).toBe(step);
      state = flowReducer(state, { type: "next" });
    }
    expect(state.step).toBe("continue");
  });

  it("goes back, jumps, and ignores unknown steps", () => {
    const state = flowReducer(initialState(), { type: "go", step: "reveal" });
    expect(state.step).toBe("reveal");
    expect(flowReducer(state, { type: "back" }).step).toBe("challenge");
    expect(flowReducer(initialState(), { type: "back" }).step).toBe("welcome");
    expect(flowReducer(state, { type: "go", step: "nowhere" as never }).step).toBe("reveal");
  });

  it("toggles theme and tech view, and keeps them across a reset", () => {
    let state = flowReducer(initialState({ seed: 5 }), { type: "toggleTheme" });
    state = flowReducer(state, { type: "toggleTechView" });
    state = flowReducer(state, { type: "go", step: "chat" });
    expect(state).toMatchObject({ theme: "dark", techView: true, step: "chat" });
    const reset = flowReducer(state, { type: "reset" });
    expect(reset).toMatchObject({ theme: "dark", techView: true, step: "welcome", seed: 6 });
  });

  it("records answers, challenge times and the personality", () => {
    let state = flowReducer(initialState(), { type: "answer", questionId: "q1", optionId: "b" });
    state = flowReducer(state, { type: "setChallengeTime", which: "before", ms: 42000 });
    state = flowReducer(state, { type: "setChallengeTime", which: "after", ms: 3000 });
    state = flowReducer(state, {
      type: "setPersonality",
      personality: { type: "Weekend Explorer", interests: ["travel", "food", "music"] },
    });
    expect(state.quizAnswers).toEqual({ q1: "b" });
    expect(state.challenge).toEqual({ targetId: null, beforeMs: 42000, afterMs: 3000 });
    expect(state.personality?.interests).toHaveLength(3);
  });

  it("clears the story after a retaken quiz but keeps the answers, the look and the seed", () => {
    const chat = {
      id: "c1",
      libraryId: "c1",
      title: "t",
      question: "q",
      reply: "r",
      paraphrase: "p",
      interest: "alpha",
      threadId: null,
      date: "2026-02-03T10:00:00.000Z",
      mine: false,
    };
    let state = flowReducer(initialState({ seed: 9, theme: "dark" }), {
      type: "answer",
      questionId: "q1",
      optionId: "a",
    });
    state = flowReducer(state, { type: "setHistory", chats: [chat] });
    state = flowReducer(state, { type: "addMyChat", chat: { ...chat, id: "mine", mine: true } });
    state = flowReducer(state, { type: "setNow", now: "2026-10-16T12:00:00.000Z" });
    state = flowReducer(state, { type: "setChallengeTarget", targetId: "mine" });
    state = flowReducer(state, { type: "setChallengeTime", which: "before", ms: 5000 });
    state = flowReducer(state, {
      type: "setBundling",
      result: { bundles: [], loose: [], placements: {}, steps: [], embedMs: 0, decisionMs: 0 },
    });
    state = flowReducer(state, { type: "go", step: "quiz" });
    const cleared = flowReducer(state, { type: "clearStory" });
    expect(cleared).toMatchObject({
      step: "quiz",
      quizAnswers: { q1: "a" },
      history: [],
      myChats: [],
      challenge: { targetId: null, beforeMs: null, afterMs: null },
      bundling: null,
      theme: "dark",
      seed: 9,
    });
    expect(cleared.now).toBeUndefined();
  });
});
