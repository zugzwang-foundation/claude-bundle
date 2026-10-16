import { APP_NAME } from "../config";
import { useFlow } from "../state/flow";
import { ProgressDots } from "./ProgressDots";
import "./Header.css";

export function Header() {
  const { state, dispatch } = useFlow();
  const dark = state.theme === "dark";
  return (
    <header className="header">
      <p className="header__brand">
        <span className="header__mark" aria-hidden="true" />
        <span className="header__name">{APP_NAME}</span>
      </p>
      <ProgressDots />
      <div className="header__switches">
        <button
          type="button"
          className="switch"
          aria-pressed={dark}
          onClick={() => dispatch({ type: "toggleTheme" })}
        >
          Dark theme
        </button>
        <button
          type="button"
          className="switch"
          aria-pressed={state.techView}
          onClick={() => dispatch({ type: "toggleTechView" })}
        >
          Tech view
        </button>
      </div>
    </header>
  );
}
