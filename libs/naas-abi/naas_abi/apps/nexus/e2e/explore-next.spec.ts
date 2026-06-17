import { expect, test, type Page } from '@playwright/test'

// Use system Chrome (Playwright's bundled chromium isn't downloaded in this environment).
test.use({ channel: 'chrome' })

// The Next dev server compiles routes on first hit and shares the box with whoever else is
// using it, so the `load` event can be slow — navigate on `domcontentloaded` and run serially.
test.describe.configure({ mode: 'serial' })
test.setTimeout(120_000)

const WEB = process.env.WEB_URL || 'http://localhost:3000'
const ADMIN_EMAIL = process.env.NEXUS_ADMIN_EMAIL || 'admin@example.com'
const ADMIN_PASSWORD = process.env.NEXUS_ADMIN_PASSWORD || 'admin'
const WORKSPACE = process.env.NEXUS_WORKSPACE || 'ws-3e360b19bb96'
const GRAPH_LABEL = process.env.NEXUS_GRAPH_LABEL || 'Test Compiler'
const CLASS_URI = process.env.NEXUS_CLASS_URI || 'http://ontology.naas.ai/documents#ExtractedItem'

async function login(page: Page): Promise<void> {
  page.setDefaultNavigationTimeout(90_000)
  await page.goto(`${WEB}/auth/login`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  await page.fill('input[type="email"]', ADMIN_EMAIL)
  await page.fill('input[type="password"]', ADMIN_PASSWORD)
  await page.click('button[type="submit"]')
  await page.waitForURL((url) => !url.pathname.includes('/auth/login'), { timeout: 60_000 })
}

async function openExplore(page: Page): Promise<void> {
  await login(page)
  await page.goto(`${WEB}/workspace/${WORKSPACE}/graph/explore-next`, {
    waitUntil: 'domcontentloaded',
    timeout: 90_000,
  })
  await expect(page.getByTestId('explore-workbench')).toBeVisible({ timeout: 60_000 })
}

/** Pick the graph + anchor class (by value, which auto-waits for the option) and wait for rows. */
async function anchor(page: Page): Promise<void> {
  await page.getByTestId('explore-graph-select').selectOption({ label: GRAPH_LABEL })
  // selectOption by value auto-waits for the async-loaded <option> to appear + be enabled.
  await page.getByTestId('explore-class-select').selectOption(CLASS_URI, { timeout: 30_000 })
  await expect(page.getByTestId('explore-row').first()).toBeVisible({ timeout: 30_000 })
}

test('anchors a class and renders backend-driven rows', async ({ page }) => {
  await openExplore(page)
  await anchor(page)

  // Columns auto-seed from /columns discovery.
  await expect(page.getByTestId('explore-columns')).toBeVisible()
  const rowCount = await page.getByTestId('explore-row').count()
  expect(rowCount).toBeGreaterThan(0)

  // The count footer reports the exact total from the backend.
  await expect(page.getByTestId('explore-count')).toContainText('rows')
})

test('sorts a column without error', async ({ page }) => {
  await openExplore(page)
  await anchor(page)
  const firstHeaderSort = page.locator('[data-testid^="column-sort-"]').first()
  await firstHeaderSort.click()
  // Sorting re-runs the query; rows should still be present and no error surfaced.
  await expect(page.getByTestId('explore-row').first()).toBeVisible({ timeout: 15_000 })
  await expect(page.getByTestId('explore-error')).toHaveCount(0)
})

test('saves a view and lists it in the sidebar', async ({ page }) => {
  await openExplore(page)
  await anchor(page)

  const viewName = `e2e view ${Date.now()}`
  await page.getByTestId('explore-save').click()
  await expect(page.getByTestId('save-view-dialog')).toBeVisible()
  await page.getByTestId('save-view-name').fill(viewName)
  await page.getByTestId('save-view-confirm').click()
  await expect(page.getByTestId('save-view-dialog')).toBeHidden({ timeout: 15_000 })

  // It appears in the saved-views sidebar.
  const item = page.getByTestId('explore-views-sidebar').getByText(viewName, { exact: false })
  await expect(item).toBeVisible({ timeout: 15_000 })

  // Clean up: delete the view we created so the test is idempotent.
  const row = page.getByTestId('explore-views-sidebar').locator('div', { hasText: viewName }).first()
  await row.hover()
  const deleteBtn = page.locator('[data-testid^="view-delete-"]').first()
  await deleteBtn.click()
  await expect(page.getByTestId('explore-views-sidebar').getByText(viewName, { exact: false })).toHaveCount(0, {
    timeout: 15_000,
  })
})
