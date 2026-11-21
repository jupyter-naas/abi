import { expect, test, type Page } from '@playwright/test'
import { WEB, signIn } from './sign-in'

/**
 * The access model's web side (#1588): a workspace is created with its workspace admin, and its
 * offer ("<W> access") is edited with toggles.
 *
 * Runs against a live stack (`abi dev up`) signed in as `NEXUS_ADMIN_EMAIL`, an admin of the
 * organization `NEXUS_E2E_ORG` (its id). Skipped without `NEXUS_E2E_ORG`. Optional:
 * `NEXUS_E2E_WORKSPACE_ADMIN`, the email of another person of that organization to make the new
 * workspace's admin (the creator otherwise).
 */

// Use system Chrome (Playwright's bundled chromium isn't downloaded in this environment).
test.use({ channel: 'chrome' })
test.describe.configure({ mode: 'serial' })
test.setTimeout(180_000)

const ORG = process.env.NEXUS_E2E_ORG || ''
const ADMIN = process.env.NEXUS_E2E_WORKSPACE_ADMIN || ''

test.skip(!ORG, 'NEXUS_E2E_ORG (an organization the signed-in admin administers) is not set')

const name = `E2E access ${Date.now()}`
let workspaceId = ''

async function open(page: Page, path: string): Promise<void> {
  await page.goto(`${WEB}${path}`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
}

test('creates a workspace with its workspace admin', async ({ page }) => {
  await signIn(page)
  await open(page, `/organizations/${ORG}/settings/workspaces/new`)
  await page.getByLabel('Workspace name').fill(name)

  // The picker names the workspace admin: the creator by default, no Owner anywhere.
  const picker = page.locator('[data-field="workspace-admin"] button[aria-haspopup="listbox"]')
  await expect(picker).toHaveAttribute('aria-label', /^Workspace admin: /, { timeout: 30_000 })
  await expect(page.getByText('Owner', { exact: true })).toHaveCount(0)
  if (ADMIN) {
    await picker.click()
    await page.getByRole('combobox', { name: 'Search organization members' }).fill(ADMIN)
    await page.getByRole('option', { name: new RegExp(ADMIN.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click()
    await expect(picker).toHaveAttribute('aria-label', new RegExp(`Workspace admin: .*${ADMIN.split('@')[0]}`))
  }

  const created = page.waitForResponse(
    (r) => r.url().endsWith('/api/workspaces') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Create workspace' }).click()
  const response = await created
  expect(response.status()).toBeLessThan(300)
  const body = JSON.parse(response.request().postData() || '{}')
  expect(body.admin_id).toBeTruthy()
  expect(body).not.toHaveProperty('owner_id')
  workspaceId = (await response.json()).id
  await expect(page).toHaveURL(new RegExp(`/organizations/${ORG}/settings/workspaces$`))

  // Its groups come first in Access, the workspace's admins among them.
  await open(page, `/workspace/${workspaceId}/settings/groups`)
  await expect(page.locator('[data-access-levels]')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('[data-group-kind="workspace-admins"]').first()).toBeVisible()
})

test('edits the workspace offer with toggles', async ({ page }) => {
  test.skip(!workspaceId, 'the workspace of the previous test was not created')
  await signIn(page)
  await open(page, `/workspace/${workspaceId}/settings/policies`)
  const offerRow = page.locator('[data-policy]:has([data-workspace-offer])').first()
  await expect(offerRow).toBeVisible({ timeout: 60_000 })
  await offerRow.click()

  const editor = page.getByRole('region', { name: 'Workspace offer' })
  await expect(editor).toBeVisible({ timeout: 30_000 })
  const feature = editor.locator('[data-offer-feature] [role="switch"]:not([disabled])').first()
  await expect(feature).toBeVisible()
  const before = await feature.getAttribute('aria-checked')

  await feature.click()
  await expect(editor.getByText('1 unsaved change')).toBeVisible()
  await editor.getByRole('button', { name: 'Save offer' }).click()
  await expect(editor.getByText('Saved')).toBeVisible({ timeout: 30_000 })
  await expect(feature).toHaveAttribute('aria-checked', before === 'true' ? 'false' : 'true')

  // Back as it was.
  await feature.click()
  await editor.getByRole('button', { name: 'Save offer' }).click()
  await expect(editor.getByText('Saved')).toBeVisible({ timeout: 30_000 })
  await expect(feature).toHaveAttribute('aria-checked', before ?? 'false')
})
