import { cpSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, '..');
const cesiumSrc = join(root, 'node_modules', 'cesium', 'Build', 'Cesium');
const dest = join(root, 'public', 'cesium');

if (!existsSync(cesiumSrc)) {
  console.warn('Cesium build directory not found, skipping asset copy.');
  process.exit(0);
}

mkdirSync(dest, { recursive: true });

for (const dir of ['Workers', 'Assets', 'Widgets', 'ThirdParty']) {
  const src = join(cesiumSrc, dir);
  if (existsSync(src)) {
    console.log(`Copying cesium/${dir}...`);
    cpSync(src, join(dest, dir), { recursive: true });
  }
}

console.log('✓ Cesium assets copied to public/cesium/');
