import { test, expect } from '@playwright/test';

const WEB_URL = process.env.WEB_URL || 'http://localhost:3042';
const API_URL = process.env.API_URL || 'http://localhost:9879';
const ADMIN_EMAIL = process.env.NEXUS_ADMIN_EMAIL || 'admin@example.com';
const ADMIN_PASSWORD = process.env.NEXUS_ADMIN_PASSWORD || 'Admin1234!';

async function loginViaApi(page: import('@playwright/test').Page) {
  const res = await page.request.post(`${API_URL}/api/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  });
  expect(res.ok()).toBeTruthy();
  const body = await res.json();
  const token = body.access_token as string;
  const user = body.user;

  const wsRes = await page.request.get(`${API_URL}/api/workspaces`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(wsRes.ok()).toBeTruthy();
  const workspaces = await wsRes.json();
  const workspaceId = workspaces[0]?.id as string;
  expect(workspaceId).toBeTruthy();

  await page.goto(`${WEB_URL}/auth/login`);
  await page.evaluate(
    ({ token, user, workspaceId }) => {
      localStorage.setItem(
        'nexus-auth',
        JSON.stringify({
          state: {
            user,
            token,
            refreshToken: null,
            isAuthenticated: true,
          },
          version: 0,
        }),
      );
      document.cookie = 'nexus-auth-flag=true; path=/; max-age=2592000';
      localStorage.setItem('nexus-workspace', JSON.stringify({
        state: { currentWorkspaceId: workspaceId },
        version: 0,
      }));
    },
    { token, user, workspaceId },
  );

  await page.goto(`${WEB_URL}/workspace/${workspaceId}/code`);
  return workspaceId as string;
}

test.describe('Code Section IDE', () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test('loads Code page with empty state and terminal panel', async ({ page }) => {
    await expect(page.getByText('No file open')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('main').getByRole('button', { name: 'New File', exact: true })).toBeVisible();
    await expect(page.getByText('Terminal')).toBeVisible();
    await expect(page.getByText('Logs')).toBeVisible();
  });

  test('creates, edits, and saves a sandbox file in Monaco', async ({ page }) => {
    const filename = `e2e_test_${Date.now()}.py`;

    await page.getByRole('main').getByRole('button', { name: 'New File', exact: true }).click();
    await page.locator('input[type="text"]').last().fill(filename);
    await page.getByRole('button', { name: 'Create' }).last().click();

    await expect(page.getByRole('main').getByText(filename, { exact: true })).toBeVisible({ timeout: 15000 });

    const editor = page.locator('.monaco-editor');
    await expect(editor).toBeVisible({ timeout: 15000 });
    await editor.click();
    await page.keyboard.type('print("code e2e ok")');

    await expect(page.locator('text=●').first()).toBeVisible({ timeout: 5000 });

    await page.keyboard.press('Meta+s');
    await page.waitForTimeout(1500);

    const token = await page.evaluate(() => {
      const raw = localStorage.getItem('nexus-auth');
      if (!raw) return null;
      try {
        const parsed = JSON.parse(raw) as { state?: { token?: string } };
        return parsed.state?.token ?? null;
      } catch {
        return null;
      }
    });
    expect(token).toBeTruthy();

    const listRes = await page.request.get(`${API_URL}/api/files/?path=code&scope=my_drive`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(listRes.ok()).toBeTruthy();
    const listedPath = (await listRes.json()).path as string;
    expect(listedPath).toBeTruthy();

    const filePath = `${listedPath}/${filename}`;
    const res = await page.request.get(
      `${API_URL}/api/files/${encodeURIComponent(filePath)}?scope=my_drive`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(body.content).toContain('code e2e ok');
  });

  test('shows markdown split preview for .md files', async ({ page }) => {
    const filename = `e2e_readme_${Date.now()}.md`;

    await page.getByRole('main').getByRole('button', { name: 'New File', exact: true }).click();
    await page.locator('input[type="text"]').last().fill(filename);
    await page.getByRole('button', { name: 'Create' }).last().click();

    await expect(page.locator('.monaco-editor')).toBeVisible({ timeout: 15000 });
    await page.locator('.monaco-editor').click();
    await page.keyboard.type('# E2E Preview\n\nHello **Code** section');

    await expect(page.getByRole('heading', { name: 'E2E Preview' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Hello Code section')).toBeVisible();
  });

  test('opens AI assistant pane on Code section', async ({ page }) => {
    await expect(
      page.locator('aside').filter({ hasText: /OpenCode|Coding|Assistant|Build|Plan/i }).first(),
    ).toBeVisible({ timeout: 15000 });
  });
});
