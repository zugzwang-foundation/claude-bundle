import { Panel } from "./Panel";
import { bestSorter, formatMetric, getLatestRun, METRICS, shortHash } from "./scoreboard";

const TOY_NOTE =
  "Toy scale: a handful of invented people, one laptop, a few minutes of training. Enough to prove the loop runs end to end, not enough to trust the numbers.";

/** The latest published exam run as a table, or a plain line when none exists. */
export function Scoreboard() {
  const run = getLatestRun();

  if (!run) {
    return (
      <Panel id="tech-board" title="Scoreboard" wide summary="no run yet">
        <p className="tech__note">No exam run published yet.</p>
        <p className="tech__muted">
          When the pipeline sits the sealed exam it writes one JSON file per run to scoreboard/runs/
          at the repository root, and this table fills itself at the next build. The first runs will
          be labelled “toy scale”. {TOY_NOTE}
        </p>
      </Panel>
    );
  }

  const notes = Array.from(new Set(run.notes));

  return (
    <Panel id="tech-board" title="Scoreboard" wide summary={run.label}>
      <p className="board__meta">
        <span className="badge">{run.label}</span>
        <span>run {run.runId}</span>
        {run.date && <span>{run.date}</span>}
        {run.baseModel && <span>base {run.baseModel}</span>}
        {run.examHash && <span title={run.examHash}>exam {shortHash(run.examHash)}</span>}
      </p>
      {run.label === "toy scale" && <p className="tech__muted">{TOY_NOTE}</p>}
      {/* biome-ignore lint/a11y/noNoninteractiveTabindex: a table that scrolls sideways on phones must be reachable from the keyboard */}
      <section className="tech__scroll" tabIndex={0} aria-labelledby="tech-board-caption">
        <table className="board__table">
          <caption id="tech-board-caption">
            Every sorter on the board, latest run. The best value in each row is in bold.
          </caption>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              {run.sorters.map((s) => (
                <th key={s.id} scope="col">
                  {s.id}
                  {s.name !== s.id && <small>{s.name}</small>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS.map((metric) => {
              const best = bestSorter(run, metric);
              return (
                <tr key={metric.key}>
                  <th scope="row" title={metric.hint}>
                    {metric.label}
                  </th>
                  {run.sorters.map((s) => {
                    const isBest = best === s.id;
                    return (
                      <td key={s.id} className={isBest ? "is-best" : undefined}>
                        {formatMetric(metric.unit, s.metrics[metric.key])}
                        {isBest && <span className="visually-hidden"> (best)</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      {notes.length > 0 && (
        <>
          <h4 className="board__h4">Notes from the run</h4>
          <ul className="board__notes">
            {notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
