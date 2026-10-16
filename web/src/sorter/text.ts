/**
 * The text that stands for a chat when it is embedded. The precompute script
 * (scripts/precompute-embeddings.mjs) imports this file directly, so the
 * build-time vectors and the live ones come from the same words.
 */
export function chatText(chat: { title: string; question: string }): string {
  return `${chat.title}\n${chat.question}`;
}
