#!/usr/bin/env node
// financial-cockpit kickstart — one command to make the template runnable:
//   1. create config/config.yaml   (from config.example.yaml — the editable app config)
//   2. create .env                 (from .env.example, with a fresh random SESSION_SECRET
//                                   and ROOT_PASSWORD)
// Idempotent: existing files are kept, never overwritten. Run with `--force` to
// regenerate .env (rotates SESSION_SECRET → invalidates existing sessions).
import { existsSync, copyFileSync, readFileSync, writeFileSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const force = process.argv.includes('--force');
const rel = (p) => p.replace(`${root}/`, '');
const log = (m) => console.log(`  ${m}`);

console.log('\n🚀 financial-cockpit kickstart\n');

// 1. config.yaml
const config = join(root, 'config', 'config.yaml');
if (!existsSync(config)) {
  copyFileSync(join(root, 'config', 'config.example.yaml'), config);
  log(`✓ created ${rel(config)} (edit this for pages, sections, banners, users)`);
} else {
  log(`• ${rel(config)} already exists — kept`);
}

// 2. .env — both secrets random, never a value the template ships.
const env = join(root, '.env');
let rootPassword = null;
if (!existsSync(env) || force) {
  let txt = readFileSync(join(root, '.env.example'), 'utf8');
  const secret = randomBytes(48).toString('base64url');
  rootPassword = randomBytes(18).toString('base64url');
  txt = txt.replace(/^SESSION_SECRET=.*$/m, `SESSION_SECRET=${secret}`);
  txt = txt.replace(/^ROOT_PASSWORD=.*$/m, `ROOT_PASSWORD=${rootPassword}`);
  writeFileSync(env, txt, { mode: 0o600 });
  log(`✓ ${force && existsSync(env) ? 'regenerated' : 'created'} ${rel(env)} with a random SESSION_SECRET and ROOT_PASSWORD`);
} else {
  log(`• ${rel(env)} already exists — kept (use --force to rotate both secrets)`);
}

console.log('\nDone. Next steps:\n');
console.log('  npm install');
console.log('  npm run dev\n');
console.log('  Then open http://localhost:3000/login and sign in with the');
if (rootPassword) {
  console.log(`  root password:  ${rootPassword}  (kept in ${rel(env)} as ROOT_PASSWORD)\n`);
} else {
  console.log(`  root password in ${rel(env)} (ROOT_PASSWORD)\n`);
}
console.log('  Demo data lives in ./data — edit it or point DATA_LOCAL_ROOT at your own.\n');
