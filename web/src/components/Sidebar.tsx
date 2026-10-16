import { type ReactNode, useEffect, useId, useMemo, useRef } from "react";
import type { HistoryChat } from "../content/types";
import "./Sidebar.css";

export interface MonthGroup {
  /** "2026-10" */
  key: string;
  /** "October 2026" */
  label: string;
  /** Newest first. */
  chats: HistoryChat[];
}

const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });
const DAY_FORMAT = new Intl.DateTimeFormat("en-GB", { day: "numeric" });

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Chats grouped by calendar month, newest month and newest chat first. */
export function groupByMonth(chats: readonly HistoryChat[]): MonthGroup[] {
  const sorted = chats.slice().sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  const groups: MonthGroup[] = [];
  for (const chat of sorted) {
    const date = new Date(chat.date);
    const key = monthKey(date);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.chats.push(chat);
    else groups.push({ key, label: MONTH_FORMAT.format(date), chats: [chat] });
  }
  return groups;
}

export interface SidebarProps {
  chats: readonly HistoryChat[];
  /** The fixed "today" (ISO 8601): chats on that day are labelled "Today". */
  now?: string;
  title?: string;
  /** A line under the title, e.g. "Nine months of chats, written for a Weekend Explorer". */
  note?: string;
  /** Rendered in the head under the note, e.g. a button. */
  action?: ReactNode;
  /** When given, every row is a button and the selected one is marked. */
  onSelect?: (chat: HistoryChat) => void;
  selectedId?: string | null;
  emptyText?: string;
  className?: string;
}

/**
 * The visitor's chat list: our own design, a long scroll grouped by month with a
 * short title and the day on each row. Rows are plain text unless `onSelect` is set.
 */
export function Sidebar({
  chats,
  now,
  title = "Your chats",
  note,
  action,
  onSelect,
  selectedId = null,
  emptyText = "No chats yet.",
  className,
}: SidebarProps) {
  const id = useId();
  const groups = useMemo(() => groupByMonth(chats), [chats]);
  const today = useMemo(() => (now ? new Date(now) : null), [now]);

  return (
    <aside className={cx("sidebar", className)} aria-labelledby={`${id}-title`}>
      <div className="sidebar__head">
        <h2 id={`${id}-title`} className="sidebar__title">
          {title}
          <span className="sidebar__count">
            {chats.length}
            <span className="visually-hidden"> chats</span>
          </span>
        </h2>
        {note && <p className="sidebar__note">{note}</p>}
        {action && <div className="sidebar__action">{action}</div>}
      </div>
      <section
        className="sidebar__scroll"
        aria-label={`${title}, grouped by month`}
        // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrolling region must be reachable from the keyboard
        tabIndex={0}
      >
        {groups.length === 0 && <p className="sidebar__empty">{emptyText}</p>}
        {groups.map((group) => (
          <section
            key={group.key}
            className="sidebar__month"
            aria-labelledby={`${id}-${group.key}`}
          >
            <h3 id={`${id}-${group.key}`} className="sidebar__month-title">
              <span>{group.label}</span>
              <span className="sidebar__month-count" aria-hidden="true">
                {group.chats.length}
              </span>
            </h3>
            <ul className="sidebar__list">
              {group.chats.map((chat) => {
                const date = new Date(chat.date);
                const day = today && sameDay(date, today) ? "Today" : DAY_FORMAT.format(date);
                const row = (
                  <>
                    <span
                      className={cx("sidebar__dot", chat.mine && "sidebar__dot--mine")}
                      aria-hidden="true"
                    />
                    <span className="sidebar__item-title">{chat.title}</span>
                    {chat.mine && <span className="sidebar__tag">you</span>}
                    <time className="sidebar__day" dateTime={chat.date}>
                      {day}
                    </time>
                  </>
                );
                return (
                  <li key={chat.id} className="sidebar__item">
                    {onSelect ? (
                      <button
                        type="button"
                        className="sidebar__row sidebar__row--button"
                        aria-current={chat.id === selectedId ? "true" : undefined}
                        onClick={() => onSelect(chat)}
                      >
                        {row}
                      </button>
                    ) : (
                      <div className="sidebar__row">{row}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </section>
    </aside>
  );
}

export interface SidebarDrawerProps extends SidebarProps {
  /** The drawer's id, for the toggle's aria-controls. */
  id: string;
  open: boolean;
  onClose: () => void;
  label?: string;
}

/**
 * The sidebar as a modal drawer for phones, on a native <dialog>: Escape, focus
 * trapping and the backdrop come from the browser; a tap outside also closes it.
 */
export function SidebarDrawer({
  id,
  open,
  onClose,
  label = "Your chats",
  ...sidebar
}: SidebarDrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    const onBackdrop = (event: MouseEvent) => {
      if (event.target === dialog) onClose();
    };
    dialog.addEventListener("click", onBackdrop);
    return () => dialog.removeEventListener("click", onBackdrop);
  }, [onClose]);

  return (
    <dialog ref={ref} id={id} className="drawer" aria-label={label} onClose={onClose}>
      <div className="drawer__panel">
        <button type="button" className="drawer__close" onClick={onClose}>
          Close
        </button>
        <Sidebar {...sidebar} className="sidebar--drawer" />
      </div>
    </dialog>
  );
}
