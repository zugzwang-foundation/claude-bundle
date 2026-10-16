// Embeds every library chat with the same model, dtype and text as the browser,
// and writes src/generated/library-embeddings.json. Skips the work when the
// library and model have not changed since the last run.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { env, pipeline } from "@huggingface/transformers";
import { chatText } from "../src/sorter/text.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const manifest = JSON.parse(readFileSync(join(root, "src/sorter/model-manifest.json"), "utf8"));
const libraryDir = join(root, "src/content/library");
const outDir = join(root, "src/generated");
const outPath = join(outDir, "library-embeddings.json");
const DECIMALS = 5;

const chats = [];
for (const file of readdirSync(libraryDir).sort()) {
  if (!file.endsWith(".json") || file === "library.schema.json") continue;
  const data = JSON.parse(readFileSync(join(libraryDir, file), "utf8"));
  for (const thread of data.threads ?? []) chats.push(...thread.chats);
  chats.push(...(data.oneOffs ?? []));
}

const hash = createHash("sha256")
  .update(
    JSON.stringify({
      model: manifest.id,
      dtype: manifest.dtype,
      decimals: DECIMALS,
      texts: chats.map((chat) => [chat.id, chatText(chat)]),
    }),
  )
  .digest("hex");

if (existsSync(outPath)) {
  try {
    const previous = JSON.parse(readFileSync(outPath, "utf8"));
    if (previous.hash === hash) {
      console.log(`precompute: up to date (${chats.length} chats, ${manifest.id})`);
      process.exit(0);
    }
  } catch {
    // Rewrite a damaged file.
  }
}

mkdirSync(outDir, { recursive: true });

if (chats.length === 0) {
  writeFileSync(
    outPath,
    `${JSON.stringify({ model: manifest.id, dtype: manifest.dtype, dim: 0, count: 0, hash, vectors: {} }, null, 0)}\n`,
  );
  console.log("precompute: no library files yet; wrote an empty embeddings file");
  process.exit(0);
}

if (manifest.source === "local") {
  env.allowLocalModels = true;
  env.allowRemoteModels = false;
  env.localModelPath = join(root, "public", "models");
}

const started = Date.now();
const extractor = await pipeline("feature-extraction", manifest.id, { dtype: manifest.dtype });
const vectors = {};
let dim = 0;
const BATCH = 32;
for (let i = 0; i < chats.length; i += BATCH) {
  const batch = chats.slice(i, i + BATCH);
  const output = await extractor(
    batch.map((chat) => chatText(chat)),
    { pooling: "mean", normalize: true },
  );
  dim = output.dims[1];
  const rows = output.tolist();
  batch.forEach((chat, j) => {
    vectors[chat.id] = rows[j].map((x) => Number(x.toFixed(DECIMALS)));
  });
}

const result = {
  model: manifest.id,
  dtype: manifest.dtype,
  dim,
  count: chats.length,
  hash,
  vectors,
};
writeFileSync(outPath, `${JSON.stringify(result)}\n`);
console.log(
  `precompute: ${chats.length} chats, ${dim} dims, ${manifest.id} (${manifest.dtype}) in ${Date.now() - started} ms -> ${outPath}`,
);
