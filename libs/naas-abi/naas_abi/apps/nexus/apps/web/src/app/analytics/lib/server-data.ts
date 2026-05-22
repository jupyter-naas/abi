import 'server-only';

import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { AnalyticsEvent } from './types';

// Read-side helpers only. Writes go through the Nexus API
// (POST /api/analytics/events on port 9879), which persists via ABI's object
// storage service and mirrors back to this directory.
const DATA_DIR = path.join(process.cwd(), 'src/app/analytics/data');
const EVENTS_PATH = path.join(DATA_DIR, 'events.json');
const REF_USERS_PATH = path.join(DATA_DIR, 'ref-users.json');
const REF_WORKSPACES_PATH = path.join(DATA_DIR, 'ref-workspaces.json');

interface RefUser {
  user_id: string;
  user_email: string;
  workspace_ids: string[];
}

interface RefWorkspace {
  workspace_id: string;
  workspace_name: string;
}

async function readJson<T>(p: string, fallback: T): Promise<T> {
  try {
    const raw = await fs.readFile(p, 'utf8');
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export async function readEvents(): Promise<AnalyticsEvent[]> {
  const data = await readJson<{ events: AnalyticsEvent[] }>(EVENTS_PATH, { events: [] });
  return Array.isArray(data.events) ? data.events : [];
}

export async function readRefUsers(): Promise<RefUser[]> {
  return readJson<RefUser[]>(REF_USERS_PATH, []);
}

export async function readRefWorkspaces(): Promise<RefWorkspace[]> {
  return readJson<RefWorkspace[]>(REF_WORKSPACES_PATH, []);
}
