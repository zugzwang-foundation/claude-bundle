#!/usr/bin/env node
// Validates demo library files against library.schema.json plus the rules the schema cannot express:
// word limits, slot syntax, unique ids, id prefixes, and a banned-word list for brands and real names.
// Usage: node web/scripts/validate-library.mjs [file.json ...]   (no args: every file in web/src/content/library)
import { readFileSync, readdirSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const libDir = resolve(here, "../src/content/library");
const schema = JSON.parse(readFileSync(join(libDir, "library.schema.json"), "utf8"));
const interests = schema.properties.interest.enum;

const BANNED = [
  // brands and products (lower case, matched as whole words)
  "spotify","apple","iphone","android","google","youtube","netflix","amazon","nike","adidas","peloton","strava","garmin","fitbit",
  "ikea","airbnb","uber","tesla","microsoft","windows","excel","chatgpt","openai","claude","anthropic","gemini","grok","facebook",
  "instagram","tiktok","twitter","whatsapp","reddit","starbucks","mcdonald","coca","pepsi","visa","mastercard","paypal","bitcoin",
  "disney","marvel","pokemon","nintendo","playstation","xbox","lego","dyson","samsung","sony","canon","nikon","gopro","kindle",
  // real people and artists are hard to list; the critic pass checks those.
];

const words = (s) => s.replace(/\{\{chat:\d\}\}/g, "slot slot").trim().split(/\s+/).filter(Boolean).length;

function check(file) {
  const errors = [];
  const data = JSON.parse(readFileSync(file, "utf8"));
  const name = basename(file, ".json");
  const e = (m) => errors.push(`${name}: ${m}`);
  if (!interests.includes(data.interest)) e(`interest "${data.interest}" not in enum`);
  if (data.interest !== name) e(`file name should equal interest (${data.interest})`);
  if (typeof data.label !== "string" || data.label.length < 3 || data.label.length > 24) e("label length");
  const allowed = new Set(["interest", "label", "threads", "oneOffs"]);
  for (const k of Object.keys(data)) if (!allowed.has(k)) e(`unexpected key ${k}`);
  if (!Array.isArray(data.threads) || data.threads.length !== 3) e("threads must have exactly 3 items");
  if (!Array.isArray(data.oneOffs) || data.oneOffs.length !== 6) e("oneOffs must have exactly 6 items");
  const ids = new Set();
  const texts = new Set();
  const chatCheck = (c, expectedId, where) => {
    const keys = ["id", "title", "question", "reply", "paraphrase"];
    for (const k of keys) if (typeof c[k] !== "string" || !c[k].trim()) e(`${where}: missing ${k}`);
    for (const k of Object.keys(c)) if (!keys.includes(k)) e(`${where}: unexpected key ${k}`);
    if (c.id !== expectedId) e(`${where}: id should be ${expectedId}, got ${c.id}`);
    if (ids.has(c.id)) e(`${where}: duplicate id ${c.id}`); ids.add(c.id);
    const tw = words(c.title || "");
    if (tw < 2 || tw > 7) e(`${where}: title should be 2-7 words (${tw})`);
    if ((c.title || "").length > 48) e(`${where}: title over 48 chars`);
    if (words(c.reply || "") > 60) e(`${where}: reply over 60 words (${words(c.reply)})`);
    if ((c.question || "").length > 220) e(`${where}: question over 220 chars`);
    if ((c.paraphrase || "").length > 160) e(`${where}: paraphrase over 160 chars`);
    if (c.paraphrase && c.question && c.paraphrase.trim().toLowerCase() === c.question.trim().toLowerCase()) e(`${where}: paraphrase equals question`);
    for (const k of ["question", "reply", "paraphrase", "title"]) {
      const key = (c[k] || "").trim().toLowerCase();
      if (texts.has(k + ":" + key)) e(`${where}: duplicate ${k} text`); texts.add(k + ":" + key);
      for (const w of (c[k] || "").toLowerCase().match(/[a-z]+/g) || []) if (BANNED.includes(w)) e(`${where}: banned word "${w}" in ${k}`);
    }
  };
  (data.threads || []).forEach((t, ti) => {
    const tid = `${data.interest}-t${ti + 1}`;
    const where = `thread ${ti + 1}`;
    if (t.id !== tid) e(`${where}: id should be ${tid}`);
    if (typeof t.topic !== "string" || t.topic.length < 4 || t.topic.length > 60) e(`${where}: topic length`);
    for (const k of Object.keys(t)) if (!["id", "topic", "chats", "continuation"].includes(k)) e(`${where}: unexpected key ${k}`);
    if (!Array.isArray(t.chats) || t.chats.length !== 8) e(`${where}: must have exactly 8 chats`);
    (t.chats || []).forEach((c, ci) => chatCheck(c, `${tid}-c${ci + 1}`, `${where} chat ${ci + 1}`));
    const cont = t.continuation || {};
    if (typeof cont.question !== "string" || cont.question.length < 8) e(`${where}: continuation.question`);
    if (typeof cont.reply !== "string") e(`${where}: continuation.reply`);
    else {
      const slots = [...cont.reply.matchAll(/\{\{chat:(\d)\}\}/g)].map((m) => Number(m[1]));
      if (slots.length < 2 || slots.length > 4) e(`${where}: continuation needs 2-4 slots (${slots.length})`);
      for (const n of slots) if (n < 1 || n > 8) e(`${where}: slot {{chat:${n}}} out of range`);
      if (new Set(slots).size !== slots.length) e(`${where}: repeated slot`);
      if (/\{\{(?!chat:\d\}\})/.test(cont.reply)) e(`${where}: malformed slot`);
      if (words(cont.reply) > 80) e(`${where}: continuation over 80 words (${words(cont.reply)})`);
      for (const w of cont.reply.toLowerCase().match(/[a-z]+/g) || []) if (BANNED.includes(w)) e(`${where}: banned word "${w}" in continuation`);
    }
  });
  (data.oneOffs || []).forEach((c, i) => chatCheck(c, `${data.interest}-o${i + 1}`, `one-off ${i + 1}`));
  return errors;
}

const files = process.argv.slice(2).length
  ? process.argv.slice(2).map((f) => resolve(f))
  : readdirSync(libDir).filter((f) => f.endsWith(".json") && f !== "library.schema.json").map((f) => join(libDir, f));
let total = 0;
for (const f of files) {
  let errs;
  try { errs = check(f); } catch (err) { errs = [`${basename(f)}: ${err.message}`]; }
  total += errs.length;
  for (const m of errs) console.error("ERROR", m);
  if (!errs.length) console.log(`ok ${basename(f)}`);
}
if (!files.length) { console.error("no library files found"); process.exit(1); }
process.exit(total ? 1 : 0);
