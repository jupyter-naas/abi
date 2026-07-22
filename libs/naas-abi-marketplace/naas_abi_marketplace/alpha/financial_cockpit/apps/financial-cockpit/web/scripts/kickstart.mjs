#!/usr/bin/env node
// financial-cockpit kickstart — one command to make the template runnable:
//   1. create config/config.yaml   (from config.example.yaml — the editable app config)
//   2. create .env                 (from .env.example, with a fresh random SESSION_SECRET)
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

// 2. .env
const env = join(root, '.env');
let adminPassword = 'demo';
if (!existsSync(env) || force) {
  let txt = readFileSync(join(root, '.env.example'), 'utf8');
  const secret = randomBytes(48).toString('base64url');
  txt = txt.replace(/^SESSION_SECRET=.*$/m, `SESSION_SECRET=${secret}`);
  if (/^ADMIN_PASSWORD=\s*$/m.test(txt)) {
    txt = txt.replace(/^ADMIN_PASSWORD=\s*$/m, `ADMIN_PASSWORD=${adminPassword}`);
  } else {
    const m = txt.match(/^ADMIN_PASSWORD=(.*)$/m);
    if (m && m[1].trim()) adminPassword = m[1].trim();
  }
  writeFileSync(env, txt);
  log(`✓ ${force && existsSync(env) ? 'regenerated' : 'created'} ${rel(env)} with a random SESSION_SECRET`);
} else {
  const m = readFileSync(env, 'utf8').match(/^ADMIN_PASSWORD=(.*)$/m);
  if (m && m[1].trim()) adminPassword = m[1].trim();
  log(`• ${rel(env)} already exists — kept (use --force to rotate the secret)`);
}

console.log('\nDone. Next steps:\n');
console.log('  npm install');
console.log('  npm run dev\n');
console.log('  Then open http://localhost:3000/login and sign in with the');
console.log(`  demo password:  ${adminPassword}\n`);
console.log('  Demo data lives in ./data — edit it or point DATA_LOCAL_ROOT at your own.\n');
