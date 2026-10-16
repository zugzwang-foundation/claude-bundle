import type { CSSProperties, ReactNode, RefCallback } from "react";
import type { HistoryChat } from "../content/types";
import "./BundleCard.css";

/** The five bundle colours, cycled in order of creation; "loose" is the grey for unsorted chats. */
export const BUNDLE_COLOURS = ["teal", "blue", "saffron", "rose", "plum"] as const;
export type BundleColour = (typeof BUNDLE_COLOURS)[number] | "loose";

/** The colour of the n-th bundle (0-based): teal, blue, saffron, rose, plum, then round again. */
export function bundleColour(index: number): BundleColour {
  const n = BUNDLE_COLOURS.length;
  return BUNDLE_COLOURS[((index % n) + n) % n] ?? "teal";
}

/** A probability as a whole percentage, e.g. 0.914 -> "91%". */
export function formatPercent(probability: number): string {
  return `${Math.round(Math.min(1, Math.max(0, probability)) * 100)}%`;
}

export interface BundleCardChat {
  chat: HistoryChat;
  /** The sorter's probability for this placement, 0 to 1. Omitted for loose chats. */
  probability?: number;
  /** True when the sorter only suggested the placement: a dashed outline and a tag. */
  suggested?: boolean;
}

export interface BundleCardProps {
  id: string;
  name: string;
  colour: BundleColour;
  chats: BundleCardChat[];
  /** When true the chats sit behind a toggle in the heading. */
  collapsible?: boolean;
  open?: boolean;
  onToggle?: (open: boolean) => void;
  /** When set, each chat is a button that calls this. */
  onChatSelect?: (chat: HistoryChat) => void;
  /** The chat to highlight, e.g. the one just found. */
  selectedChatId?: string | null;
  /** A chat to nudge briefly as the wrong pick. */
  wrongChatId?: string | null;
  /** Returns a ref for a chat's row so the screen can animate it moving in. */
  rowRef?: (chatId: string) => RefCallback<HTMLLIElement>;
  /** Stagger the rows' entrance in CSS; off when the screen animates rows itself. */
  animateRows?: boolean;
  headingLevel?: 2 | 3;
  /** Extra content under the chats, such as a note. */
  children?: ReactNode;
  className?: string;
}

type VarStyle = CSSProperties & { [key: `--${string}`]: string | number };

/**
 * One bundle: a coloured stripe, its name and count, and the chats inside.
 * Filed chats show their percentage; suggested ones get a dashed outline; the
 * grey "loose" variant lists chats the sorter left alone.
 */
export function BundleCard({
  id,
  name,
  colour,
  chats,
  collapsible = false,
  open,
  onToggle,
  onChatSelect,
  selectedChatId = null,
  wrongChatId = null,
  rowRef,
  animateRows = false,
  headingLevel = 3,
  children,
  className = "",
}: BundleCardProps) {
  const Heading: "h2" | "h3" = headingLevel === 2 ? "h2" : "h3";
  const titleId = `${id}-title`;
  const bodyId = `${id}-chats`;
  const isOpen = collapsible ? open !== false : true;
  const total = chats.length;
  const classes = ["bundle-card", colour === "loose" ? "bundle-card--loose" : "", className]
    .filter(Boolean)
    .join(" ");

  const title = (
    <>
      <span className="bundle-card__dot" aria-hidden="true" />
      <span className="bundle-card__name">{name}</span>
      <span className="bundle-card__count">
        {total} {total === 1 ? "chat" : "chats"}
      </span>
    </>
  );

  return (
    <article className={classes} data-colour={colour} data-bundle-id={id} aria-labelledby={titleId}>
      <header className="bundle-card__head">
        {collapsible ? (
          <Heading className="bundle-card__title" id={titleId}>
            <button
              type="button"
              className="bundle-card__toggle"
              aria-expanded={isOpen}
              aria-controls={bodyId}
              onClick={() => onToggle?.(!isOpen)}
            >
              {title}
              <span className="bundle-card__chevron" aria-hidden="true" />
            </button>
          </Heading>
        ) : (
          <Heading className="bundle-card__title bundle-card__title--static" id={titleId}>
            {title}
          </Heading>
        )}
      </header>
      <ul id={bodyId} className="bundle-card__chats" hidden={!isOpen}>
        {chats.map(({ chat, probability, suggested }, index) => {
          const selected = selectedChatId === chat.id;
          const wrong = wrongChatId === chat.id;
          const style: VarStyle | undefined = animateRows ? { "--i": index } : undefined;
          return (
            <li
              key={chat.id}
              ref={rowRef?.(chat.id)}
              className="bundle-card__row"
              data-chat-id={chat.id}
              data-suggested={suggested ? "" : undefined}
              data-selected={selected ? "" : undefined}
              data-wrong={wrong ? "" : undefined}
              data-enter={animateRows ? "" : undefined}
              style={style}
            >
              {onChatSelect ? (
                <button
                  type="button"
                  className="bundle-card__chat"
                  aria-current={selected ? "true" : undefined}
                  onClick={() => onChatSelect(chat)}
                >
                  {chat.title}
                </button>
              ) : (
                <span className="bundle-card__chat" aria-current={selected ? "true" : undefined}>
                  {chat.title}
                </span>
              )}
              <span className="bundle-card__meta">
                {suggested && <span className="bundle-card__tag">suggested</span>}
                {probability !== undefined && (
                  <span className="bundle-card__pct">{formatPercent(probability)}</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      {children}
    </article>
  );
}
