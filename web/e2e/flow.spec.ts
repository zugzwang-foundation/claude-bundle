import { mkdirSync, writeFileSync } from "node:fs";
import { expect, type Locator, type Page, test } from "@playwright/test";
import { APP_NAME, FOOTER_TEXT } from "../src/config";

/** Screenshots of every step go here; set BDL_SCREENS_DIR for the session folder. */
const SCREENS_DIR = process.env.BDL_SCREENS_DIR ?? "test-results/screens";
/** Measured budgets (model bytes, ms per decision) are written here, one file per run. */
const BUDGETS_DIR = "test-results/budgets";
/** The only third-party hosts a visit may touch: the model download and its CDN. */
const MODEL_HOSTS = /(^|\.)(huggingface\.co|hf\.co)$/;
const QUIZ_QUESTIONS = 7;
const CHAT_TAPS = 3;
/** The model is fetched from huggingface.co in the test browser; allow two minutes for it. */
const MODEL_TIMEOUT_MS = 120_000;

interface NetworkWatch {
  /** Hosts outside this origin and the model hosts; every request to them was aborted. */
  otherHosts: Set<string>;
  /** Bytes of 200 responses from the model hosts, from their Content-Length headers. */
  modelBytes: number;
  modelResponses: number;
  modelFiles: string[];
}

interface BundleStats {
  count: number;
  medianMs: number;
  meanMs: number;
  p95Ms: number;
  maxMs: number;
  embedMs: number;
  decisionMs: number;
  bundles: number;
  loose: number;
  device: string | null;
  model: string | null;
  sizeBytes: number | null;
  loadMs: number | null;
}

/** Let the page talk to itself and to the model hosts; abort and record anything else. */
async function watchNetwork(page: Page): Promise<NetworkWatch> {
  const watch: NetworkWatch = {
    otherHosts: new Set(),
    modelBytes: 0,
    modelResponses: 0,
    modelFiles: [],
  };
  await page.route(/^https?:\/\//, (route) => {
    const { hostname } = new URL(route.request().url());
    if (hostname === "localhost" || hostname === "127.0.0.1" || MODEL_HOSTS.test(hostname)) {
      return route.continue();
    }
    watch.otherHosts.add(hostname);
    return route.abort();
  });
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (!MODEL_HOSTS.test(url.hostname) || response.status() !== 200) return;
    const length = Number(response.headers()["content-length"] ?? 0);
    if (length > 0) {
      watch.modelBytes += length;
      watch.modelResponses += 1;
      watch.modelFiles.push(`${url.pathname.split("/").slice(-2).join("/")} ${length}`);
    }
  });
  return watch;
}

const STOPWORDS = new Set(
  "a an the and or of to for in on at by with from my your our his her their is are was do does how what when where which who why that this these those as about into over".split(
    " ",
  ),
);

/** The first word of a title worth typing into a search box: four letters or more, not a stopword. */
function firstDistinctiveWord(title: string): string {
  const words = title
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
  const pick = words.find((word) => word.length >= 4 && !STOPWORDS.has(word));
  return pick ?? words.sort((a, b) => b.length - a.length)[0] ?? title;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function shot(page: Page, project: string, theme: string, index: number, step: string) {
  mkdirSync(SCREENS_DIR, { recursive: true });
  await page.screenshot({
    path: `${SCREENS_DIR}/${project}-${theme}-${String(index).padStart(2, "0")}-${step}.png`,
    fullPage: true,
  });
}

async function expandAll(bundles: Locator) {
  const closed = bundles.locator(".bundle-card__toggle[aria-expanded='false']");
  for (let guard = 0; guard < 40; guard += 1) {
    if ((await closed.count()) === 0) return;
    await closed.first().click();
  }
}

for (const theme of ["light", "dark"] as const) {
  test(`walks the whole story in ${theme}`, async ({ page }, testInfo) => {
    const project = testInfo.project.name;
    const watch = await watchNetwork(page);
    const footer = page.getByRole("contentinfo");
    const expectFooter = async () => expect(footer).toContainText(FOOTER_TEXT);

    await page.goto("/?test");
    await expect(page).toHaveTitle(APP_NAME);
    if (theme === "dark") await page.getByRole("button", { name: "Dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);

    // 1. Welcome: one line and a start button.
    const welcome = page.locator('[data-step="welcome"]');
    await expect(welcome.getByRole("heading", { level: 1 })).toBeVisible();
    await expectFooter();
    await shot(page, project, theme, 1, "welcome");
    await welcome.getByRole("button", { name: "Start" }).click();

    // 2. Quiz: seven taps, then a type and interests.
    const quiz = page.locator('[data-step="quiz"]');
    await expect(quiz).toBeVisible();
    await expect(quiz.getByText(`Question 1 of ${QUIZ_QUESTIONS}`)).toBeVisible();
    await expectFooter();
    await shot(page, project, theme, 2, "quiz");
    for (let q = 1; q <= QUIZ_QUESTIONS; q += 1) {
      await expect(quiz.getByText(`Question ${q} of ${QUIZ_QUESTIONS}`)).toBeVisible();
      const options = quiz.locator(".quiz__option");
      await expect(options).toHaveCount(4);
      await options.nth(q % 4).click();
    }
    const build = quiz.getByRole("button", { name: "Build my history" });
    await expect(build).toBeVisible();
    await expect(quiz.locator(".quiz__chips li")).not.toHaveCount(0);
    await shot(page, project, theme, 2, "quiz-result");
    await build.click();

    // 3. History: 100 to 150 chats over nine months.
    const history = page.locator('[data-step="history"]');
    await expect(history).toBeVisible();
    const items = history.locator(".sidebar__item");
    await expect.poll(() => items.count()).toBeGreaterThanOrEqual(100);
    const historyCount = await items.count();
    expect(historyCount).toBeLessThanOrEqual(150);
    await expectFooter();
    await shot(page, project, theme, 3, "history");
    await history.getByRole("button", { name: "Start a new chat" }).click();

    // 4. Chat: tap three ready-made questions and watch the replies type.
    const chat = page.locator('[data-step="chat"]');
    await expect(chat).toBeVisible();
    for (let i = 0; i < CHAT_TAPS; i += 1) {
      const chips = chat.locator(".chat__chips button");
      await expect(chips.first()).toBeVisible();
      await chips.first().click();
      await expect(chat.locator(".msg--reply")).toHaveCount(i + 1);
      await expect(chat.locator(".typing__caret")).toHaveCount(0, { timeout: 60_000 });
    }
    await expect(chat.locator(".msg--reply").last()).not.toBeEmpty();
    await expectFooter();
    await shot(page, project, theme, 4, "chat");
    await chat.getByRole("button", { name: "Fast-forward a few months" }).click();

    // 5. Months pass: the clock runs; skip ahead.
    const months = page.locator('[data-step="months"]');
    await expect(months).toBeVisible();
    await expectFooter();
    await shot(page, project, theme, 5, "months");
    const skip = months.getByRole("button", { name: "Skip" });
    if (await skip.isVisible().catch(() => false)) await skip.click().catch(() => undefined);

    // 6. Challenge: find the chat by its paraphrase, with title search.
    const challenge = page.locator('[data-step="challenge"]');
    await expect(challenge).toBeVisible();
    const paraphrase = (await challenge.getByTestId("challenge-paraphrase").innerText()).trim();
    expect(paraphrase.length).toBeGreaterThan(0);
    const targetTitle = await challenge
      .getByRole("heading", { level: 1 })
      .getAttribute("data-target-title");
    if (!targetTitle) throw new Error("the challenge heading carries no data-target-title");
    await expect(challenge.getByRole("timer")).toBeVisible();
    const word = firstDistinctiveWord(targetTitle);
    await challenge.getByLabel("Search your chats").fill(word);
    const match = challenge.locator(".challenge__chat").filter({
      has: page.locator(".challenge__chat-title", {
        hasText: new RegExp(`^\\s*${escapeRegExp(targetTitle)}\\s*$`),
      }),
    });
    await expect(match.first()).toBeVisible();
    await expectFooter();
    await shot(page, project, theme, 6, "challenge");
    await match.first().click();

    // 7. Reveal: one switch; the model downloads and sorts every chat.
    const reveal = page.locator('[data-step="reveal"]');
    await expect(reveal).toBeVisible();
    await expect(reveal).toHaveAttribute("data-phase", "off");
    await expectFooter();
    await shot(page, project, theme, 7, "reveal");
    await reveal.getByRole("switch", { name: "Bundle my chats" }).click();
    await expect(reveal).toHaveAttribute("data-phase", "find", {
      timeout: MODEL_TIMEOUT_MS + 60_000,
    });
    const bundles = reveal.locator(".reveal__bundles");
    await expect(bundles.locator(".bundle-card")).not.toHaveCount(0);
    expect(await bundles.locator(".bundle-card:not(.bundle-card--loose)").count()).toBeGreaterThan(
      0,
    );
    await expectFooter();
    await shot(page, project, theme, 7, "reveal-bundles");

    // Find it again, inside the bundles this time.
    await expandAll(bundles);
    await bundles.getByRole("button", { name: targetTitle, exact: true }).first().click();
    await expect(reveal).toHaveAttribute("data-phase", "done");
    await expect(reveal.locator(".reveal__headline")).toContainText(/Before: .+ After: .+/);
    await shot(page, project, theme, 7, "reveal-found");
    const stats = await page.evaluate(() => window.__bundleStats ?? null);
    expect(stats).not.toBeNull();
    await reveal.getByRole("button", { name: "Carry on" }).click();

    // 8. Continue: the found chat inside its bundle; the reply names bundle chats.
    const cont = page.locator('[data-step="continue"]');
    await expect(cont).toBeVisible();
    await expect(cont.locator(".bundle-card")).toHaveCount(1);
    await cont.locator(".continue__question").click();
    const reply = cont.getByTestId("continue-reply");
    await expect(reply).toBeVisible();
    expect(await reply.locator("mark").count()).toBeGreaterThanOrEqual(1);
    await expectFooter();
    await shot(page, project, theme, 8, "continue");

    // The tech view, with the sort's measurements, for the record.
    const tech = page.getByRole("button", { name: "Tech view" });
    await tech.click();
    await expect(tech).toHaveAttribute("aria-pressed", "true");
    const panel = page.getByRole("complementary", { name: "Tech view" });
    await expect(panel).toBeVisible();
    const perDecision = await panel
      .getByText(/median .*ms, mean .*ms, max .*ms/)
      .first()
      .innerText()
      .catch(() => "");
    await shot(page, project, theme, 9, "tech-view");

    // Record the measured budgets for README.md.
    mkdirSync(BUDGETS_DIR, { recursive: true });
    writeFileSync(
      `${BUDGETS_DIR}/${project}-${theme}.json`,
      `${JSON.stringify(
        {
          project,
          theme,
          historyCount,
          targetTitle,
          paraphrase,
          modelBytes: watch.modelBytes,
          modelMB: Number((watch.modelBytes / 1_048_576).toFixed(2)),
          modelResponses: watch.modelResponses,
          modelFiles: watch.modelFiles,
          stats: stats as BundleStats | null,
          perDecision,
          otherHosts: [...watch.otherHosts],
        },
        null,
        2,
      )}\n`,
    );

    // Privacy: nothing left the origin except the model download.
    expect([...watch.otherHosts]).toEqual([]);
  });
}

test("the start button works from the keyboard and the tech view toggles", async ({ page }) => {
  const watch = await watchNetwork(page);
  await page.goto("/");
  const start = page.locator('[data-step="welcome"]').getByRole("button", { name: "Start" });
  await start.focus();
  await expect(start).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator('[data-step="quiz"]')).toBeVisible();

  const tech = page.getByRole("button", { name: "Tech view" });
  await expect(tech).toHaveAttribute("aria-pressed", "false");
  await tech.click();
  await expect(tech).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("complementary", { name: "Tech view" })).toBeVisible();
  expect([...watch.otherHosts]).toEqual([]);
});
