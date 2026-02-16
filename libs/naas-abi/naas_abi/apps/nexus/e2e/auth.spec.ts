import { test, expect } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8000';
const WEB_URL = process.env.WEB_URL || 'http://localhost:3000';

test.describe('Authentication Flow', () => {
  test('should complete full registration flow', async ({ page }) => {
    const timestamp = Date.now();
    const email = `test-${timestamp}@example.com`;
    
    // Navigate to app
    await page.goto(WEB_URL);
    
    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
    
    // Click register link
    await page.click('text=Sign up');
    
    // Fill registration form
    await page.fill('input[name="email"]', email);
    await page.fill('input[name="name"]', 'Test User');
    await page.fill('input[name="password"]', 'TestPass123!');
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Should redirect to workspaces or create workspace
    await page.waitForURL(/\/workspace/, { timeout: 10000 });
    
    // Verify logged in
    await expect(page.locator('text=Test User')).toBeVisible();
  });

  test('should login with existing user', async ({ page }) => {
    await page.goto(`${WEB_URL}/login`);
    
    // Fill login form
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'nexus2026');
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Should redirect to workspaces
    await page.waitForURL(/\/workspace/);
    
    // Verify user name visible
    await expect(page.locator('text=Jeremy Ravenel')).toBeVisible();
  });

  test('should fail login with wrong password', async ({ page }) => {
    await page.goto(`${WEB_URL}/login`);
    
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'wrongpassword');
    
    await page.click('button[type="submit"]');
    
    // Should show error
    await expect(page.locator('text=/Invalid credentials|incorrect/i')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto(`${WEB_URL}/login`);
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'nexus2026');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/workspace/);
    
    // Logout
    await page.click('[data-testid="user-menu"]');
    await page.click('text=Logout');
    
    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe('Workspace Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto(`${WEB_URL}/login`);
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'nexus2026');
    await page.click('button[type="submit"]');
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
    await page.goto(`${WEB_URL}/login`);
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'nexus2026');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/workspace/);
  });

  test('should send message and receive response', async ({ page }) => {
    // Navigate to chat
    await page.goto(`${WEB_URL}/workspace/workspace-nexus/chat`);
    
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
    await page.goto(`${WEB_URL}/workspace/workspace-nexus/chat`);
    
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
    await page.goto(`${WEB_URL}/login`);
    await page.fill('input[name="email"]', 'jeremy@naas.ai');
    await page.fill('input[name="password"]', 'nexus2026');
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/workspace/);
  });

  test('should display knowledge graph', async ({ page }) => {
    await page.goto(`${WEB_URL}/workspace/workspace-nexus/graph`);
    
    // Should see graph canvas
    await expect(page.locator('[data-testid="graph-canvas"]')).toBeVisible();
    
    // Should have nodes
    const nodeCount = await page.locator('[data-node="true"]').count();
    expect(nodeCount).toBeGreaterThan(0);
  });

  test('should search and filter nodes', async ({ page }) => {
    await page.goto(`${WEB_URL}/workspace/workspace-nexus/graph`);
    
    // Search for node
    await page.fill('[data-testid="graph-search"]', 'NEXUS Platform');
    
    // Should highlight matching node
    await expect(page.locator('[data-node-highlight="true"]')).toBeVisible();
  });
});
