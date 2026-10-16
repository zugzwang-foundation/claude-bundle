/**
 * The personality quiz: seven playful taps, scored over the library's twelve
 * interests, ending in an original personality type and three to five interests.
 * Pure data and pure functions; the Quiz screen renders them.
 * No real characters, celebrities or brands appear in the copy.
 */

export const INTERESTS = [
  "fitness",
  "travel",
  "food",
  "money",
  "work",
  "study",
  "music",
  "home",
  "pets",
  "tech",
  "health",
  "parenting",
] as const;

export type Interest = (typeof INTERESTS)[number];

/** Short labels for the interest chips; the library's own labels can replace them later. */
export const INTEREST_LABELS: Record<Interest, string> = {
  fitness: "Fitness",
  travel: "Travel",
  food: "Food",
  money: "Money",
  work: "Work",
  study: "Study",
  music: "Music",
  home: "Home",
  pets: "Pets",
  tech: "Tech",
  health: "Health",
  parenting: "Parenting",
};

/** How much one tap counts towards each interest. Three for the main one, one for a nudge. */
export type Weights = Partial<Record<Interest, number>>;

export interface QuizOption {
  id: string;
  text: string;
  weights: Weights;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: QuizOption[];
}

export const QUESTIONS: QuizQuestion[] = [
  {
    id: "q1",
    prompt: "It's Saturday morning and nobody needs you for an hour. You…",
    options: [
      {
        id: "a",
        text: "Lace up and get moving before the day has an opinion",
        weights: { fitness: 3, health: 1 },
      },
      {
        id: "b",
        text: "Make something slow and buttery for breakfast",
        weights: { food: 3, home: 1 },
      },
      { id: "c", text: "Open a map and plan a trip you may never take", weights: { travel: 3 } },
      { id: "d", text: "Finally fix the thing that squeaks", weights: { home: 3, tech: 1 } },
    ],
  },
  {
    id: "q2",
    prompt: "Your phone buzzes with a notification you're actually glad to see. It's…",
    options: [
      {
        id: "a",
        text: "A bill that came in lower than you feared",
        weights: { money: 3, home: 1 },
      },
      { id: "b", text: "A friend sending a song with no explanation", weights: { music: 3 } },
      {
        id: "c",
        text: "A photo of somebody's dog doing nothing in particular",
        weights: { pets: 3 },
      },
      { id: "d", text: "The meeting moved. The meeting is gone.", weights: { work: 3, study: 1 } },
    ],
  },
  {
    id: "q3",
    prompt: "A free evening and an empty sofa. On the screen is…",
    options: [
      { id: "a", text: "The course you keep meaning to finish", weights: { study: 3, work: 1 } },
      { id: "b", text: "A recipe video you'll pause twelve times", weights: { food: 3, home: 1 } },
      {
        id: "c",
        text: "A stretching routine, because your back has started commenting",
        weights: { fitness: 2, health: 2 },
      },
      {
        id: "d",
        text: "A family film and far too many cushions",
        weights: { parenting: 3, home: 1 },
      },
    ],
  },
  {
    id: "q4",
    prompt: "Your browser tabs, honestly:",
    options: [
      {
        id: "a",
        text: "Trains, ferries and a hostel with suspicious reviews",
        weights: { travel: 3 },
      },
      {
        id: "b",
        text: "Three spreadsheets and a pension calculator",
        weights: { money: 3, work: 1 },
      },
      { id: "c", text: "Docs, a terminal and something half-built", weights: { tech: 3, work: 1 } },
      { id: "d", text: "Symptoms you really shouldn't have searched", weights: { health: 3 } },
    ],
  },
  {
    id: "q5",
    prompt: "A small windfall lands in your lap. It becomes…",
    options: [
      { id: "a", text: "Decent running shoes, at last", weights: { fitness: 3, health: 1 } },
      { id: "b", text: "Dinner out, with pudding, no debate", weights: { food: 3 } },
      {
        id: "c",
        text: "A plant you will absolutely keep alive this time",
        weights: { home: 3, money: 1 },
      },
      { id: "d", text: "A toy the dog will destroy by Tuesday", weights: { pets: 3 } },
    ],
  },
  {
    id: "q6",
    prompt: "Pick the sound of a good day:",
    options: [
      {
        id: "a",
        text: "The kettle, a nap, and a small person finally asleep",
        weights: { parenting: 3, home: 1 },
      },
      { id: "b", text: "Headphones on, the world off", weights: { music: 3 } },
      { id: "c", text: "Pages turning in a very quiet library", weights: { study: 3 } },
      {
        id: "d",
        text: "Keyboard clatter as a plan finally comes together",
        weights: { work: 3, tech: 1 },
      },
    ],
  },
  {
    id: "q7",
    prompt: "The question you'd most likely ask an assistant at 11 pm:",
    options: [
      {
        id: "a",
        text: "Is it normal for my knee to click like that?",
        weights: { health: 3, fitness: 1 },
      },
      {
        id: "b",
        text: "Why does my code do that, and how do I make it stop?",
        weights: { tech: 3, work: 1 },
      },
      { id: "c", text: "Is it too late to start a pension?", weights: { money: 3 } },
      {
        id: "d",
        text: "How do I explain 'budget' to a seven-year-old?",
        weights: { parenting: 3, money: 1 },
      },
    ],
  },
];

export interface PersonalityType {
  id: string;
  /** An original name, e.g. "Weekend Explorer". */
  name: string;
  /** One playful line. */
  tagline: string;
  /** The interests this type leans towards, strongest first. */
  interests: Interest[];
}

/** Twelve original types. Every interest appears in at least two of them. */
export const PERSONALITY_TYPES: PersonalityType[] = [
  {
    id: "weekend-explorer",
    name: "Weekend Explorer",
    tagline: "Boots by the door, snacks in the bag, and a map that's mostly optimism.",
    interests: ["travel", "fitness", "food"],
  },
  {
    id: "kitchen-tinkerer",
    name: "Kitchen Tinkerer",
    tagline: "Every recipe is a first draft, and the kitchen is the lab.",
    interests: ["food", "home", "health"],
  },
  {
    id: "quiet-planner",
    name: "Quiet Planner",
    tagline: "Keeps a spreadsheet for the spreadsheets, and honestly, it helps.",
    interests: ["money", "work", "study"],
  },
  {
    id: "late-night-builder",
    name: "Late-Night Builder",
    tagline: "Something is always half-built, and the headphones are always on.",
    interests: ["tech", "music", "study"],
  },
  {
    id: "steady-striver",
    name: "Steady Striver",
    tagline: "Small reps, long games, and a calendar that actually gets used.",
    interests: ["fitness", "health", "work"],
  },
  {
    id: "cosy-nester",
    name: "Cosy Nester",
    tagline: "Home is the project, and it is lovingly never finished.",
    interests: ["home", "pets", "parenting"],
  },
  {
    id: "curious-scholar",
    name: "Curious Scholar",
    tagline: "Has a tab open about everything and fully intends to read them all.",
    interests: ["study", "tech", "money"],
  },
  {
    id: "playlist-wanderer",
    name: "Playlist Wanderer",
    tagline: "Measures journeys in albums and cities in record shops.",
    interests: ["music", "travel", "tech"],
  },
  {
    id: "pack-leader",
    name: "Pack Leader",
    tagline: "Someone in the house always needs feeding, walking or finding.",
    interests: ["pets", "fitness", "parenting"],
  },
  {
    id: "careful-carer",
    name: "Careful Carer",
    tagline: "Reads the label, then reads it again, then asks a follow-up.",
    interests: ["health", "parenting", "food"],
  },
  {
    id: "thrifty-maker",
    name: "Thrifty Maker",
    tagline: "Fixes it, flips it or finds a cheaper one before buying new.",
    interests: ["money", "home", "tech"],
  },
  {
    id: "rhythm-keeper",
    name: "Rhythm Keeper",
    tagline: "Runs to a beat, cooks to a beat, and sleeps to a quieter one.",
    interests: ["music", "fitness", "health"],
  },
];

/** The quiz always picks at least this many interests and at most MAX_INTERESTS. */
export const MIN_INTERESTS = 3;
export const MAX_INTERESTS = 5;
/** A fourth or fifth interest needs at least one main tap (weight 3) to count. */
const EXTRA_INTEREST_MIN_SCORE = 3;

export type Answers = Record<string, string>;

export function emptyScores(): Record<Interest, number> {
  const scores = {} as Record<Interest, number>;
  for (const interest of INTERESTS) scores[interest] = 0;
  return scores;
}

/** Sum the weights of every answered option. Unknown ids are ignored. */
export function scoreAnswers(answers: Answers): Record<Interest, number> {
  const scores = emptyScores();
  for (const question of QUESTIONS) {
    const optionId = answers[question.id];
    if (!optionId) continue;
    const option = question.options.find((o) => o.id === optionId);
    if (!option) continue;
    for (const [interest, weight] of Object.entries(option.weights) as [Interest, number][]) {
      scores[interest] += weight;
    }
  }
  return scores;
}

/** Interests from highest score to lowest; ties keep the canonical order. */
export function rankInterests(scores: Record<Interest, number>): Interest[] {
  return [...INTERESTS].sort((a, b) => {
    const diff = scores[b] - scores[a];
    return diff !== 0 ? diff : INTERESTS.indexOf(a) - INTERESTS.indexOf(b);
  });
}

/** The top three interests, plus a fourth and fifth when they earned a main tap. */
export function chooseInterests(scores: Record<Interest, number>): Interest[] {
  const ranked = rankInterests(scores);
  const chosen = ranked.slice(0, MIN_INTERESTS);
  for (const interest of ranked.slice(MIN_INTERESTS, MAX_INTERESTS)) {
    if (scores[interest] >= EXTRA_INTEREST_MIN_SCORE) chosen.push(interest);
  }
  return chosen;
}

/** The type whose interests best match the chosen ones, weighted by rank. Ties keep table order. */
export function choosePersonalityType(chosen: Interest[]): PersonalityType {
  let best = PERSONALITY_TYPES[0] as PersonalityType;
  let bestScore = -1;
  for (const type of PERSONALITY_TYPES) {
    let score = 0;
    for (const interest of type.interests) {
      const rank = chosen.indexOf(interest);
      if (rank >= 0) score += MAX_INTERESTS - rank;
    }
    if (score > bestScore) {
      best = type;
      bestScore = score;
    }
  }
  return best;
}

export interface QuizResult {
  type: PersonalityType;
  interests: Interest[];
  scores: Record<Interest, number>;
}

/** Everything the result screen shows, from the answers alone. Deterministic. */
export function buildResult(answers: Answers): QuizResult {
  const scores = scoreAnswers(answers);
  const interests = chooseInterests(scores);
  const type = choosePersonalityType(interests);
  return { type, interests, scores };
}

/** "a" or "an", so the headline reads "You're an Early Riser" if a type ever starts with a vowel. */
export function indefiniteArticle(name: string): "a" | "an" {
  return /^[aeiou]/i.test(name) ? "an" : "a";
}
