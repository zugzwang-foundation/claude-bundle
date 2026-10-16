import { type ReactNode, useState } from "react";

export interface PanelProps {
  /** A stable id; the heading and body ids derive from it. */
  id: string;
  title: string;
  /** Short live text shown beside the title, outside the toggle's name. */
  summary?: ReactNode;
  defaultOpen?: boolean;
  /** Spans both columns of the tech grid on wide screens. */
  wide?: boolean;
  children: ReactNode;
}

/**
 * A collapsible section of the tech view: a level-3 heading whose button
 * toggles the body (the disclosure pattern), so every panel is reachable and
 * foldable from the keyboard.
 */
export function Panel({
  id,
  title,
  summary,
  defaultOpen = true,
  wide = false,
  children,
}: PanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const titleId = `${id}-title`;
  const bodyId = `${id}-body`;
  return (
    <section className={wide ? "panel panel--wide" : "panel"} aria-labelledby={titleId}>
      <div className="panel__head">
        <h3 className="panel__title" id={titleId}>
          <button
            type="button"
            className="panel__toggle"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((v) => !v)}
          >
            <span className="panel__chevron" aria-hidden="true" />
            <span>{title}</span>
          </button>
        </h3>
        {summary !== undefined && summary !== null && <p className="panel__summary">{summary}</p>}
      </div>
      <div id={bodyId} className="panel__body" hidden={!open}>
        {children}
      </div>
    </section>
  );
}
