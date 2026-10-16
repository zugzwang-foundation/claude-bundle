import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, type TestInfo, test } from "@playwright/test";

/**
 * The accessibility walk: every step the story reaches without waiting for the model
 * download, in both themes, with reduced motion on so nothing is mid-animation.
 * At each step: axe (WCAG 2.0, 2.1 and 2.2, levels A and AA), one h1 and no skipped
 * heading level, the step's heading holding focus after a keyboard move, and on the
 * phone every visible control at least 44 CSS pixels in both directions.
 */

const QUIZ_QUESTIONS = 7;
const CHAT_TAPS = 3;
const MIN_TARGET_PX = 44;
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

test.use({ reducedMotion: "reduce" });

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

interface TargetReport {
  label: string;
  width: number;
  height: number;
}

async function audit(page: Page, testInfo: TestInfo, where: string) {
  // Two frames, so that a theme flip or a step change has settled before anything is measured.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  const violations = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    nodes: v.nodes
      .map((n) => ({ target: n.target.join(" "), data: n.any.map((check) => check.data) }))
      .slice(0, 8),
  }));
  expect(violations, `axe at ${where}: ${JSON.stringify(violations, null, 2)}`).toEqual([]);

  // Headings: exactly one h1 and no level skipped on the way down.
  const levels = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLElement>("h1, h2, h3, h4, h5, h6"))
      .filter((h) => h.getClientRects().length > 0)
      .map((h) => Number(h.tagName.slice(1))),
  );
  expect(
    levels.filter((level) => level === 1),
    `h1 count at ${where}`,
  ).toHaveLength(1);
  for (let i = 1; i < levels.length; i += 1) {
    const previous = levels[i - 1] ?? 1;
    const current = levels[i] ?? 1;
    expect(current <= previous + 1, `heading order at ${where}: ${levels.join(" ")}`).toBe(true);
  }

  // Phone: every visible control is at least 44 by 44 CSS pixels.
  if (testInfo.project.name === "phone") {
    const small = await page.evaluate((min) => {
      const selector = 'button, input, select, textarea, a[href], [role="switch"], [tabindex="0"]';
      const out: { label: string; width: number; height: number }[] = [];
      for (const el of document.querySelectorAll<HTMLElement>(selector)) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0 || rect.bottom <= 0) continue;
        if (getComputedStyle(el).visibility === "hidden") continue;
        if (el.closest("dialog:not([open])")) continue;
        if (rect.width < min || rect.height < min) {
          const label = `${el.tagName.toLowerCase()}.${el.className.toString().split(" ")[0]}`;
          out.push({ label, width: Math.round(rect.width), height: Math.round(rect.height) });
        }
      }
      return out;
    }, MIN_TARGET_PX);
    expect(small as TargetReport[], `targets under ${MIN_TARGET_PX}px at ${where}`).toEqual([]);
  }
}

/** The new step's heading holds focus, so assistive technology lands on the new content. */
async function expectStepFocus(page: Page, step: string) {
  const section = page.locator(`[data-step="${step}"]`);
  await expect(section).toBeVisible();
  await expect(section.getByRole("heading", { level: 1 })).toBeFocused();
}

/** Activate a control from the keyboard. */
async function pressOn(page: Page, locator: ReturnType<Page["locator"]>) {
  await locator.focus();
  await expect(locator).toBeFocused();
  await page.keyboard.press("Enter");
}

for (const theme of ["light", "dark"] as const) {
  test(`every step is accessible in ${theme}`, async ({ page }, testInfo) => {
    const phone = testInfo.project.name === "phone";
    await page.goto("/?test");

    // 1. Welcome. The skip link is the first stop from the keyboard.
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
    if (theme === "dark") await page.getByRole("button", { name: "Dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const welcome = page.locator('[data-step="welcome"]');
    await audit(page, testInfo, `welcome/${theme}`);
    await pressOn(page, welcome.getByRole("button", { name: "Start" }));

    // 2. Quiz: the arrow keys move between cards; the digit keys answer.
    const quiz = page.locator('[data-step="quiz"]');
    await expectStepFocus(page, "quiz");
    const options = quiz.locator(".quiz__option");
    await options.first().focus();
    await page.keyboard.press("ArrowDown");
    await expect(options.nth(1)).toBeFocused();
    await page.keyboard.press("End");
    await expect(options.nth(3)).toBeFocused();
    await audit(page, testInfo, `quiz/${theme}`);
    for (let q = 1; q <= QUIZ_QUESTIONS; q += 1) {
      await expect(quiz.getByText(`Question ${q} of ${QUIZ_QUESTIONS}`)).toBeVisible();
      await page.keyboard.press(String((q % 4) + 1));
    }
    const build = quiz.getByRole("button", { name: "Build my history" });
    await expect(build).toBeVisible();
    await expect(quiz.getByRole("heading", { level: 1 })).toBeFocused();
    await audit(page, testInfo, `quiz-result/${theme}`);
    await pressOn(page, build);

    // 3. History.
    const history = page.locator('[data-step="history"]');
    await expectStepFocus(page, "history");
    await expect.poll(() => history.locator(".sidebar__item").count()).toBeGreaterThanOrEqual(100);
    await audit(page, testInfo, `history/${theme}`);
    await pressOn(page, history.getByRole("button", { name: "Start a new chat" }));

    // 4. Chat: the drawer on the phone opens and closes from the keyboard and gives focus back.
    const chat = page.locator('[data-step="chat"]');
    await expectStepFocus(page, "chat");
    if (phone) {
      const toggle = chat.getByRole("button", { name: /Your chats/ });
      await pressOn(page, toggle);
      const drawer = page.getByRole("dialog", { name: "Your chats" });
      await expect(drawer).toBeVisible();
      await audit(page, testInfo, `chat-drawer/${theme}`);
      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();
      await expect(toggle).toBeFocused();
    }
    for (let i = 0; i < CHAT_TAPS; i += 1) {
      await pressOn(page, chat.locator(".chat__chips button").first());
      await expect(chat.locator(".msg--reply")).toHaveCount(i + 1);
    }
    await audit(page, testInfo, `chat/${theme}`);
    await pressOn(page, chat.getByRole("button", { name: "Fast-forward a few months" }));

    // 5. Months pass, then carry on by themselves.
    await expectStepFocus(page, "months");
    await audit(page, testInfo, `months/${theme}`);

    // 6. Challenge: search from the keyboard; Enter on the one match picks it.
    const challenge = page.locator('[data-step="challenge"]');
    await expect(challenge).toBeVisible({ timeout: 20_000 });
    await expectStepFocus(page, "challenge");
    const targetTitle = await challenge
      .getByRole("heading", { level: 1 })
      .getAttribute("data-target-title");
    if (!targetTitle) throw new Error("the challenge heading carries no data-target-title");
    await challenge.getByLabel("Search your chats").fill(firstDistinctiveWord(targetTitle));
    const match = challenge.locator(".challenge__chat").filter({
      has: page.locator(".challenge__chat-title", {
        hasText: new RegExp(`^\\s*${escapeRegExp(targetTitle)}\\s*$`),
      }),
    });
    await expect(match.first()).toBeVisible();
    await audit(page, testInfo, `challenge/${theme}`);
    await pressOn(page, match.first());

    // 7. Reveal, before the switch: the long list scrolls and takes focus; the tech view opens.
    const reveal = page.locator('[data-step="reveal"]');
    await expectStepFocus(page, "reveal");
    await expect(reveal).toHaveAttribute("data-phase", "off");
    await expect(reveal.getByRole("switch", { name: "Bundle my chats" })).toBeVisible();
    await reveal.getByRole("region", { name: "The long list" }).focus();
    await expect(reveal.getByRole("region", { name: "The long list" })).toBeFocused();
    await audit(page, testInfo, `reveal/${theme}`);
    const tech = page.getByRole("button", { name: "Tech view" });
    await pressOn(page, tech);
    await expect(tech).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("complementary", { name: "Tech view" })).toBeVisible();
    await audit(page, testInfo, `reveal-tech/${theme}`);
  });
}
