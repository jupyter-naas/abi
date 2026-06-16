import { test, expect, type Page } from '@playwright/test';

// Use the system-installed Google Chrome (Playwright's bundled chromium isn't downloaded
// in this environment). Override per-file so it doesn't affect the other specs.
test.use({ channel: 'chrome' });

const WEB = process.env.WEB_URL || 'http://localhost:3000';
const ADMIN_EMAIL = process.env.NEXUS_ADMIN_EMAIL || 'admin@example.com';
const ADMIN_PASSWORD = process.env.NEXUS_ADMIN_PASSWORD || 'admin';

/** Log in as the admin user and wait until we've left the login page. */
export async function login(page: Page): Promise<void> {
  await page.goto(`${WEB}/auth/login`);
  await page.fill('input[type="email"]', ADMIN_EMAIL);
  await page.fill('input[type="password"]', ADMIN_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.includes('/auth/login'), { timeout: 30_000 });
}

test('unauthenticated root redirects to the login page', async ({ page }) => {
  await page.goto(WEB);
  await expect(page).toHaveURL(/\/auth\/login/);
  await expect(page.locator('input[type="email"]')).toBeVisible();
});

test('admin can log in', async ({ page }) => {
  await login(page);
  expect(page.url()).not.toContain('/auth/login');
});
