import { STEP_LABELS, STEPS, useFlow } from "../state/flow";
import { stepIndex } from "../state/steps";
import "./ProgressDots.css";

/** Where the visitor is in the story. Earlier steps can be revisited. */
export function ProgressDots() {
  const { state, dispatch } = useFlow();
  const current = stepIndex(state.step);
  return (
    <nav className="dots" aria-label="Steps">
      <ol className="dots__list">
        {STEPS.map((step, index) => {
          const isCurrent = index === current;
          return (
            <li key={step} className="dots__item">
              <button
                type="button"
                className="dots__dot"
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`Step ${index + 1} of ${STEPS.length}: ${STEP_LABELS[step]}`}
                disabled={index > current}
                onClick={() => dispatch({ type: "go", step })}
              />
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
