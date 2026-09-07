// Guarantees config/config.yaml exists before Next.js compiles (it is imported
// statically). Runs automatically via the predev / prebuild npm hooks, so the
// app builds even if the user forgot to run `npm run kickstart`. config.yaml is
// gitignored and generated from the committed config.example.yaml.
import { existsSync, copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const config = join(root, 'config', 'config.yaml');
const example = join(root, 'config', 'config.example.yaml');

if (!existsSync(config)) {
  copyFileSync(example, config);
  console.log('[ensure-config] created config/config.yaml from config.example.yaml');
}
