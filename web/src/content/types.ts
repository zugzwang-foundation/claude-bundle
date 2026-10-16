/** One chat in the demo library: a question, its reply, and the words used to find it later. */
export interface LibraryChat {
  id: string;
  title: string;
  question: string;
  reply: string;
  paraphrase: string;
}

/** A thread of related chats asked over several months, with a continuation for the last step. */
export interface LibraryThread {
  id: string;
  topic: string;
  chats: LibraryChat[];
  continuation: { question: string; reply: string };
}

/** One interest file from src/content/library/<interest>.json. */
export interface LibraryInterest {
  interest: string;
  label: string;
  threads: LibraryThread[];
  oneOffs: LibraryChat[];
}

/** A chat as it appears in the visitor's history, dated and attributed. */
export interface HistoryChat {
  id: string;
  libraryId: string;
  title: string;
  question: string;
  reply: string;
  paraphrase: string;
  interest: string;
  threadId: string | null;
  /** ISO 8601 timestamp. */
  date: string;
  /** True for chats the visitor asked themselves during the demo. */
  mine: boolean;
}
