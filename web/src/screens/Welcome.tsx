import { Button } from "../components/Button";
import { useFlow } from "../state/flow";
import "./Welcome.css";

/** Step 1: one line and one button. The footer is the shell's. */
export function Welcome() {
  const { dispatch } = useFlow();
  return (
    <section className="screen welcome" data-step="welcome" aria-labelledby="welcome-title">
      <h1 id="welcome-title" className="welcome__line">
        Your AI chats, sorted while you blink.
      </h1>
      <div className="screen__actions welcome__actions">
        <Button size="lg" onClick={() => dispatch({ type: "next" })}>
          Start
        </Button>
      </div>
    </section>
  );
}
