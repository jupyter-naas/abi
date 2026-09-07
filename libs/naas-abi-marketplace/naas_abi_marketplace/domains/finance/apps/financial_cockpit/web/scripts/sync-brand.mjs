// Copies brand bytes into the locations Next.js serves:
//   assets/logo.png     → public/logo.png
//   assets/favicon.ico  → app/icon.png
// Either file can stand in for the other so `npm run dev` still starts when
// one of them is missing (ABI gitignores `*.png`, so logo.png is easy to lose).
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const logoSrc = join(root, 'assets', 'logo.png');
const faviconSrc = join(root, 'assets', 'favicon.ico');
const logoDest = join(root, 'public', 'logo.png');
const iconDest = join(root, 'app', 'icon.png');

function copy(src, dest, label) {
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(src, dest);
  console.log(`[sync-brand] ${label}`);
}

const logo = existsSync(logoSrc) ? logoSrc : existsSync(faviconSrc) ? faviconSrc : null;
const icon = existsSync(faviconSrc) ? faviconSrc : existsSync(logoSrc) ? logoSrc : null;

if (logo) {
  copy(logo, logoDest, `${logo === logoSrc ? 'assets/logo.png' : 'assets/favicon.ico (fallback)'} → public/logo.png`);
} else {
  console.warn('[sync-brand] skipped public/logo.png — no assets/logo.png or assets/favicon.ico');
}

if (icon) {
  copy(icon, iconDest, `${icon === faviconSrc ? 'assets/favicon.ico' : 'assets/logo.png (fallback)'} → app/icon.png`);
} else {
  console.warn('[sync-brand] skipped app/icon.png — no assets/favicon.ico or assets/logo.png');
}
