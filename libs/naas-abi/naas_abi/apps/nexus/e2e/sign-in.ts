import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, type Page } from '@playwright/test';

/**
 * Sign-in for the e2e specs: Nexus has no password. The login page routes an email to
 * the built-in identity provider (pages under the API origin at `/idp/`), which mails a
 * 6-digit code; after the code the browser returns to Nexus with its session cookie.
 *
 * In `abi dev up` the email adapter keeps every mail as a `<epoch ms>-<id>.eml` file, so
 * the code is read from the mail directory:
 *   - `NEXUS_E2E_MAIL_DIR`, when set;
 *   - else `storage/email` of the project under test: `./storage/email` of the directory
 *     the tests run from, else of this repository's root (`abi dev up` run at the root).
 * `abi dev code --email <address>` prints the same code.
 */

export const WEB = process.env.WEB_URL || 'http://localhost:3000';
export const ADMIN_EMAIL = process.env.NEXUS_ADMIN_EMAIL || 'admin@example.com';

const CODE_TIMEOUT_MS = 30_000;
const POLL_MS = 500;
// The code page of the provider: a field named `code`; its email page: a field named `email`.
const CODE_FIELD = 'input[name="code"]';
const EMAIL_FIELD = 'input[name="email"]';

export function mailDirectory(): string {
  const configured = process.env.NEXUS_E2E_MAIL_DIR;
  if (configured) return path.resolve(configured);
  const here = path.resolve(process.cwd(), 'storage', 'email');
  if (existsSync(here)) return here;
  // libs/naas-abi/naas_abi/apps/nexus/e2e -> the repository root.
  return path.resolve(__dirname, '..', '..', '..', '..', '..', '..', 'storage', 'email');
}

/** The text of a mail: undo the transfer encoding the mail library chose. */
function decoded(raw: string): string {
  const split = raw.search(/\r?\n\r?\n/);
  const head = split < 0 ? raw : raw.slice(0, split);
  const body = split < 0 ? '' : raw.slice(split).trimStart();
  if (/content-transfer-encoding:\s*base64/i.test(head)) {
    return head + '\n' + Buffer.from(body.replace(/\s+/g, ''), 'base64').toString('utf8');
  }
  if (/content-transfer-encoding:\s*quoted-printable/i.test(head)) {
    const text = body
      .replace(/=\r?\n/g, '')
      .replace(/=([0-9A-F]{2})/gi, (_m, hex: string) => String.fromCharCode(parseInt(hex, 16)));
    return head + '\n' + text;
  }
  return raw;
}

/** The newest sign-in code mailed to `email` at or after `since` (epoch ms), if any. */
export function codeMailedTo(email: string, since: number): string | null {
  const directory = mailDirectory();
  if (!existsSync(directory)) return null;
  const wanted = email.trim().toLowerCase();
  // Names sort in sending order: `<epoch ms>-<id>.eml`.
  const names = readdirSync(directory)
    .filter((name) => /^\d+-.+\.eml$/.test(name))
    .sort()
    .reverse();
  for (const name of names) {
    if (Number(name.split('-', 1)[0]) < since) break;
    const text = decoded(readFileSync(path.join(directory, name), 'utf8'));
    const to = /^to:\s*(.*)$/im.exec(text)?.[1] ?? '';
    if (!to.toLowerCase().includes(wanted)) continue;
    const code = /sign-in code is:\s*(\d{4,10})/i.exec(text)?.[1];
    if (code) return code;
  }
  return null;
}

/** Wait for the code mailed to `email` after `since`. */
export async function waitForCode(email: string, since: number): Promise<string> {
  const deadline = Date.now() + CODE_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const code = codeMailedTo(email, since);
    if (code) return code;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
  throw new Error(`No sign-in code was mailed to ${email} in ${mailDirectory()} within 30 s`);
}

/**
 * Ask for a code: the Nexus login page, the email, and the provider's code page.
 * Returns the time the request was made, to tell its mail from older ones.
 */
export async function requestCode(page: Page, email: string = ADMIN_EMAIL): Promise<number> {
  page.setDefaultNavigationTimeout(90_000);
  await page.goto(`${WEB}/auth/login`, { waitUntil: 'domcontentloaded', timeout: 90_000 });
  await page.fill('input[type="email"]', email);
  const since = Date.now();
  await page.click('button[type="submit"]');
  // Normally straight to the code page; a provider that asks for the address again gets it.
  await page.waitForSelector(`${CODE_FIELD}, ${EMAIL_FIELD}`, { timeout: 60_000 });
  if (await page.locator(EMAIL_FIELD).count()) {
    if (!(await page.inputValue(EMAIL_FIELD))) await page.fill(EMAIL_FIELD, email);
    await page.click('button[type="submit"]');
    await page.waitForSelector(CODE_FIELD, { timeout: 30_000 });
  }
  expect(new URL(page.url()).pathname).toContain('/idp/');
  return since;
}

/** Enter a code on the provider's code page. */
export async function submitCode(page: Page, code: string): Promise<void> {
  await page.fill(CODE_FIELD, code);
  await page.click('button[type="submit"]');
}

export function leftTheLogin(url: URL): boolean {
  return !url.pathname.includes('/auth/login') && !url.pathname.includes('/idp/');
}

/** Sign in as `email` and wait until Nexus has taken the session (we left the login pages). */
export async function signIn(page: Page, { email = ADMIN_EMAIL }: { email?: string } = {}): Promise<void> {
  const since = await requestCode(page, email);
  await submitCode(page, await waitForCode(email, since));
  await page.waitForURL(leftTheLogin, { timeout: 60_000 });
}

/** Log out through the account menu: the web app ends the session (POST /api/auth/oidc/logout). */
export async function signOut(page: Page): Promise<void> {
  await page.getByRole('button', { name: /account menu/i }).first().click();
  await page.getByRole('menuitem', { name: /log out/i }).click();
  await expect(page).toHaveURL(/\/auth\/login/);
}
