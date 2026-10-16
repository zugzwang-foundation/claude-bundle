import { Panel } from "./Panel";

interface Milestone {
  id: string;
  when: string;
  now?: boolean;
  title: string;
  detail: string;
}

const MILESTONES: readonly Milestone[] = [
  {
    id: "toy",
    when: "Today",
    now: true,
    title: "The toy loop, end to end, on one laptop",
    detail:
      "A teacher model writes invented chats; a student learns from them, is calibrated, sits a sealed exam and lands on the scoreboard. This site runs the browser half of that loop.",
  },
  {
    id: "spark",
    when: "Next",
    title: "Real training on a DGX Spark",
    detail:
      "The same pipeline, run nightly on a desktop GPU box: a bigger teacher, far more lessons, and a student that is examined every morning.",
  },
  {
    id: "comparators",
    when: "Then",
    title: "Comparators on the board",
    detail:
      "Every run compares the student with a no-training baseline, its previous version, an open general decision model and a frontier small model, on accuracy, honesty of percentages, speed and size.",
  },
  {
    id: "release",
    when: "By 31 December 2026",
    title: "Public release",
    detail:
      "The model, its training data, the scoreboard history and this demo, under open licences, offered as a proposal any chat platform can adopt.",
  },
];

/** Where the project is going, with the only date the plan commits to. */
export function Roadmap() {
  return (
    <Panel id="tech-roadmap" title="Roadmap" defaultOpen={false}>
      <ol className="road">
        {MILESTONES.map((m) => (
          <li key={m.id} className={m.now ? "road__item road__item--now" : "road__item"}>
            <span className="road__when">{m.when}</span>
            <div className="road__text">
              <p className="road__title">{m.title}</p>
              <p className="road__detail">{m.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
