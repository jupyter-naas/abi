/**
 * Make brace-expansion@5.0.8 callable as `require('brace-expansion')(pattern)`
 * so legacy minimatch@3 / @8 (ESLint plugins, @node-minify) keep working.
 *
 * Needed because npm's GHSA-mh99-v99m-4gvg advisory range (`<=5.0.7`) incorrectly
 * flags already-patched 1.x/2.x, so we pin everything to 5.0.8 via overrides.
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const marker = "// Callable CJS export for legacy minimatch (GHSA-mh99-v99m-4gvg).";
const snippet = `
${marker}
module.exports = Object.assign(expand, {
  expand: exports.expand,
  EXPANSION_MAX: exports.EXPANSION_MAX,
  EXPANSION_MAX_LENGTH: exports.EXPANSION_MAX_LENGTH,
});
`;

function walk(dir, out = []) {
  let entries;
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    const path = join(dir, name);
    let st;
    try {
      st = statSync(path);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      if (name === "brace-expansion") out.push(path);
      else walk(path, out);
    }
  }
  return out;
}

let patched = 0;
for (const pkgDir of walk(join(root, "node_modules"))) {
  const cjs = join(pkgDir, "dist", "commonjs", "index.js");
  let src;
  try {
    src = readFileSync(cjs, "utf8");
  } catch {
    continue;
  }
  if (src.includes(marker)) continue;
  if (!src.includes("exports.expand") || !src.includes("function expand(")) continue;
  writeFileSync(cjs, `${src.trimEnd()}\n${snippet}`);
  patched += 1;
}

if (patched > 0) {
  console.log(`patched brace-expansion callable export in ${patched} package(s)`);
}
