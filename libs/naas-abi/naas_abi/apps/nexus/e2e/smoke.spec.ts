import { test, expect } from '@playwright/test';
import { WEB, signIn } from './sign-in';

// Use the system-installed Google Chrome (Playwright's bundled chromium isn't downloaded
// in this environment). Override per-file so it doesn't affect the other specs.
test.use({ channel: 'chrome' });

test('unauthenticated root redirects to the login page', async ({ page }) => {
  await page.goto(WEB);
  await expect(page).toHaveURL(/\/auth\/login/);
  await expect(page.locator('input[type="email"]')).toBeVisible();
});

test('admin can sign in with the code the identity provider mails', async ({ page }) => {
  await signIn(page);
  expect(page.url()).not.toContain('/auth/login');
  expect(page.url()).not.toContain('/idp/');
});
