import type { CSSProperties, HTMLAttributes } from "react";
import { type ContinuationPart, fillContinuationParts } from "../content/continuation";
import type { HistoryChat } from "../content/types";
import "./ContinuationReply.css";

export interface ContinuationReplyProps
  extends Omit<HTMLAttributes<HTMLParagraphElement>, "children"> {
  /** The thread's continuation reply, with its {{chat:N}} slots. */
  reply: string;
  /** The thread's chats in thread order (see pickContinuation). */
  threadChats: readonly HistoryChat[];
  /** Ids of the chats in the found chat's bundle (see bundleChatIdsFor). */
  bundleChatIds: ReadonlySet<string>;
  /** Already-filled parts, when the caller computed them; skips the fill. */
  parts?: ContinuationPart[];
}

/**
 * The continuation reply with each filled slot highlighted: a <mark> in
 * accent-soft shows which earlier chat of the bundle the answer leans on.
 * Dropped slots leave no trace. Plain text otherwise; pass aria-live on the
 * element if the reply arrives after the screen has rendered.
 */
export function ContinuationReply({
  reply,
  threadChats,
  bundleChatIds,
  parts,
  className,
  ...rest
}: ContinuationReplyProps) {
  const resolved = parts ?? fillContinuationParts(reply, threadChats, bundleChatIds);
  let titleIndex = 0;
  return (
    <p className={["continuation-reply", className].filter(Boolean).join(" ")} {...rest}>
      {resolved.map((part, index) => {
        if (part.kind === "text") {
          // biome-ignore lint/suspicious/noArrayIndexKey: parts are static for a given reply
          return <span key={`t${index}`}>{part.text}</span>;
        }
        const order = titleIndex;
        titleIndex += 1;
        return (
          <mark
            key={`${part.chatId}-${order}`}
            className="continuation-reply__title"
            data-chat-id={part.chatId}
            style={{ "--i": order } as CSSProperties}
          >
            {part.text}
          </mark>
        );
      })}
    </p>
  );
}
