import { promises as fs } from 'node:fs';
import path from 'node:path';
import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

// metadata.json is written by the Nexus API (Python) after every rebuild.
// We read the local mirror so the dashboard avoids a cross-origin call.
const METADATA_PATH = path.join(
  process.cwd(),
  'src/app/analytics/data/metadata.json',
);

export async function GET() {
  try {
    const raw = await fs.readFile(METADATA_PATH, 'utf8');
    return NextResponse.json(JSON.parse(raw));
  } catch {
    return NextResponse.json(null);
  }
}
