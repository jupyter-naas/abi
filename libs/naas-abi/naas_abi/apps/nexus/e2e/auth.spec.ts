import { test, expect } from '@playwright/test';
import { ADMIN_EMAIL, WEB, requestCode, signIn, signOut, submitCode } from './sign-in';

// Nexus has no password: people sign in at the identity provider with a mailed code
// (see sign-in.ts). The workspace flows below keep what they covered, behind that sign-in.

test.describe('Authentication Flow', () => {
  test('unauthenticated visitors are sent to the login page', async ({ page }) => {
    await page.goto(WEB);
    await expect(page).toHaveURL(/\/auth\/login/);
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test('should sign in with the code the provider mails', async ({ page }) => {
    await signIn(page, { email: ADMIN_EMAIL });

    // Back in the app, with a session: the root no longer sends us to the login page.
    await expect(page).not.toHaveURL(/\/auth\/login|\/idp\//);
    await page.goto(WEB);
    await expect(page).not.toHaveURL(/\/auth\/login/);
  });

  test('should stay on the code page and say so when the code is wrong', async ({ page }) => {
    await requestCode(page, ADMIN_EMAIL);

    await submitCode(page, '000000');

    // The provider asks again, with its error, and Nexus has no session.
    await expect(page.locator('input[name="code"]')).toBeVisible();
    await expect(page.locator('[role="alert"]')).toContainText(/not valid|expired/i);
    expect(new URL(page.url()).pathname).toContain('/idp/');
  });

  test('should logout successfully', async ({ page }) => {
    await signIn(page);

    await signOut(page);
  });
});

test.describe('Workspace Management', () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await page.waitForURL(/\/workspace/);
  });

  test('should list user workspaces', async ({ page }) => {
    // Should see workspace list
    await expect(page.locator('text=NEXUS')).toBeVisible();
    await expect(page.locator('text=NaasAI')).toBeVisible();
  });

  test('should create new workspace', async ({ page }) => {
    // Navigate to create workspace
    await page.click('text=New Workspace');

    // Fill form
    const workspaceName = `Test Workspace ${Date.now()}`;
    await page.fill('input[name="name"]', workspaceName);
    await page.fill('input[name="slug"]', `test-${Date.now()}`);

    // Submit
    await page.click('button[type="submit"]');

    // Should see new workspace
    await expect(page.locator(`text=${workspaceName}`)).toBeVisible();
  });

  test('should switch between workspaces', async ({ page }) => {
    // Click workspace switcher
    await page.click('[data-testid="workspace-switcher"]');

    // Select different workspace
    await page.click('text=NCOR');

    // URL should change
    await expect(page).toHaveURL(/\/workspace\/workspace-ncor/);
  });
});

test.describe('Chat Interface', () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await page.waitForURL(/\/workspace/);
  });

  test('should send message and receive response', async ({ page }) => {
    // Navigate to chat
    await page.goto(`${WEB}/workspace/workspace-nexus/chat`);

    // Type message
    await page.fill('[data-testid="chat-input"]', 'Hello, this is a test message');

    // Send
    await page.click('[data-testid="send-button"]');

    // Should see message in chat
    await expect(page.locator('text=Hello, this is a test message')).toBeVisible();

    // Should receive response
    await expect(page.locator('[data-role="assistant"]')).toBeVisible({ timeout: 10000 });
  });

  test('should switch between agents', async ({ page }) => {
    await page.goto(`${WEB}/workspace/workspace-nexus/chat`);

    // Open agent selector
    await page.click('[data-testid="agent-selector"]');

    // Select different agent
    await page.click('text=Content Assistant');

    // Verify selected
    await expect(page.locator('text=Content Assistant')).toBeVisible();
  });
});

test.describe('Graph Visualization', () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await page.waitForURL(/\/workspace/);
  });

  test('should display knowledge graph', async ({ page }) => {
    await page.goto(`${WEB}/workspace/workspace-nexus/graph`);

    // Should see graph canvas
    await expect(page.locator('[data-testid="graph-canvas"]')).toBeVisible();

    // Should have nodes
    const nodeCount = await page.locator('[data-node="true"]').count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('should search and filter nodes', async ({ page }) => {
    await page.goto(`${WEB}/workspace/workspace-nexus/graph`);

    // Search for node
    await page.fill('[data-testid="graph-search"]', 'NEXUS Platform');

    // Should highlight matching node
    await expect(page.locator('[data-node-highlight="true"]')).toBeVisible();
  });
});
