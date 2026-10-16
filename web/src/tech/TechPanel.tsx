import { useFlow } from "../state/flow";
import { ArchitectureDiagram } from "./ArchitectureDiagram";
import { ModelInfo } from "./ModelInfo";
import { Privacy } from "./Privacy";
import { ProbabilityBars } from "./ProbabilityBars";
import { Roadmap } from "./Roadmap";
import { Scoreboard } from "./ScoreboardPanel";
import "./tech.css";

/**
 * The tech view, rendered under the current step when state.techView is on.
 * Before the reveal the model panel leads; after it the probability bars do.
 * Keys keep both mounted when they swap, so their folded state survives.
 */
export function TechPanel() {
  const { state } = useFlow();
  const revealed = state.bundling !== null || state.step === "reveal" || state.step === "continue";
  const live = [<ModelInfo key="model" />, <ProbabilityBars key="bars" />];
  if (revealed) live.reverse();
  return (
    <aside className="tech" aria-labelledby="tech-title">
      <div className="tech__head">
        <p className="screen__kicker">Under the bonnet</p>
        <h2 id="tech-title">Tech view</h2>
        <p className="tech__lede">
          What the sorter is doing right now and how it was built. Every number here is measured on
          your device during this visit; nothing is sent anywhere.
        </p>
      </div>
      <div className="tech__grid">
        {live}
        <ArchitectureDiagram />
        <Scoreboard />
        <Roadmap />
        <Privacy />
      </div>
    </aside>
  );
}
