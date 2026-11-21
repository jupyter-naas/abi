import { expect, test, type Page } from '@playwright/test'
import { WEB, signIn } from './sign-in'

/**
 * The people flows (#1589): a person is given a level and groups, at the organization and from a
 * workspace, and removed from the organization.
 *
 * Runs against a live stack (`abi dev up`) signed in as `NEXUS_ADMIN_EMAIL`, an admin of the
 * organization `NEXUS_E2E_ORG` (its id), which has at least two workspaces. Skipped without
 * `NEXUS_E2E_ORG`. The people it creates are `e2e-people-<time>@example.com`.
 */

// Use system Chrome (Playwright's bundled chromium isn't downloaded in this environment).
test.use({ channel: 'chrome' })
test.describe.configure({ mode: 'serial' })
test.setTimeout(180_000)

const ORG = process.env.NEXUS_E2E_ORG || ''

test.skip(!ORG, 'NEXUS_E2E_ORG (an organization the signed-in admin administers) is not set')

const stamp = Date.now()
const ALICE = `e2e-people-${stamp}-a@example.com`
const BOB = `e2e-people-${stamp}-b@example.com`
let aliceId = ''
let workspaces: { id: string; name: string }[] = []

async function open(page: Page, path: string): Promise<void> {
  await page.goto(`${WEB}${path}`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
}

async function createAtOrg(page: Page, email: string, pick: (page: Page) => Promise<void>) {
  await open(page, `/organizations/${ORG}/settings/users/new`)
  await page.locator('#create-user-email').fill(email)
  await pick(page)
  const created = page.waitForResponse(
    (r) => r.url().endsWith(`/api/organizations/${ORG}/members/invite`) && r.request().method() === 'POST',
  )
  await page.locator('[data-action="create"]').click()
  const response = await created
  expect(response.status()).toBeLessThan(300)
  return { body: JSON.parse(response.request().postData() || '{}'), answer: await response.json() }
}

test('creates a person at the organization in two workspaces, admin of one', async ({ page }) => {
  await signIn(page)
  const listed = await page.request.get(`${WEB}/api/organizations/${ORG}/workspaces`)
  workspaces = listed.ok() ? await listed.json() : []
  test.skip(workspaces.length < 2, 'the organization has fewer than two workspaces')
  const [first, second] = workspaces

  const { body, answer } = await createAtOrg(page, ALICE, async (p) => {
    await p.locator(`[data-workspace="${first.id}"] label`).first().click()
    await p.locator(`[data-workspace="${second.id}"] label`).first().click()
    await p.getByLabel(`Admin of ${first.name}`).check()
  })
  // One request: a Member (a workspace admin is one), the two workspaces, no role, no Owner.
  expect(body.level).toBe('member')
  expect(body.workspaces).toEqual(
    expect.arrayContaining([
      { id: first.id, admin: true },
      { id: second.id, admin: false },
    ]),
  )
  expect(body).not.toHaveProperty('role')
  aliceId = answer.user.id
  await expect(page).toHaveURL(new RegExp(`/organizations/${ORG}/settings/users`))
})

test('adds a person of the organization from a workspace', async ({ page }) => {
  test.skip(workspaces.length < 2, 'the organization has fewer than two workspaces')
  await signIn(page)
  // Bob is one of the organization's people: no workspace yet.
  await createAtOrg(page, BOB, async () => {})
  const target = workspaces[1]
  await open(page, `/workspace/${target.id}/settings/users`)
  const search = page.getByRole('combobox').first()
  await search.fill(BOB)
  const added = page.waitForResponse(
    (r) => r.url().includes(`/api/workspaces/${target.id}/members`) && r.request().method() === 'POST',
  )
  await page.getByRole('option', { name: new RegExp(BOB.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click()
  const answer = await added
  expect(answer.status()).toBeLessThan(300)
  await expect(page.getByText(BOB).first()).toBeVisible({ timeout: 30_000 })
})

test('changes a level from a workspace', async ({ page }) => {
  test.skip(workspaces.length < 2, 'the organization has fewer than two workspaces')
  await signIn(page)
  const target = workspaces[1]
  await open(page, `/workspace/${target.id}/settings/users`)
  const row = page.locator('tr', { hasText: BOB })
  const level = row.locator('select[data-field="level"]')
  await expect(level).toBeVisible({ timeout: 60_000 })
  const next = (await level.inputValue()) === 'viewer' ? 'member' : 'viewer'
  const changed = page.waitForResponse(
    (r) => r.url().includes(`/api/workspaces/${target.id}/members/`) && r.request().method() === 'PATCH',
  )
  await level.selectOption(next)
  const response = await changed
  expect(response.status()).toBeLessThan(300)
  expect(JSON.parse(response.request().postData() || '{}').level).toBe(next)
  await expect(level).toHaveValue(next)
})

test('removes a person from the organization', async ({ page }) => {
  test.skip(!aliceId, 'the person of the first test was not created')
  await signIn(page)
  await open(page, `/organizations/${ORG}/settings/users/${aliceId}`)
  await page.getByRole('button', { name: 'Remove from organization' }).click()
  const removed = page.waitForResponse(
    (r) => r.url().endsWith(`/members/${encodeURIComponent(aliceId)}/access`) && r.request().method() === 'DELETE',
  )
  await page.getByRole('button', { name: 'Remove', exact: true }).click()
  const response = await removed
  expect(response.status()).toBe(200)
  const left = (await response.json()).workspace_ids as string[]
  expect(left).toEqual(expect.arrayContaining([workspaces[0].id, workspaces[1].id]))
  await expect(page).toHaveURL(new RegExp(`/organizations/${ORG}/settings/users$`))
})
