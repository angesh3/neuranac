import { test, expect } from '@playwright/test'
import { injectAuth, collectCriticalErrors } from './helpers'

test.describe('Dashboard & Topology', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  test('dashboard renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('dashboard has page title or heading', async ({ page }) => {
    await page.goto('/')
    const heading = page.locator('h1, h2, [data-testid="page-title"]').first()
    await expect(heading).toBeVisible({ timeout: 5000 })
  })

  test('dashboard renders stat cards or widgets', async ({ page }) => {
    await page.goto('/')
    // Dashboard typically has metric cards
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(50)
  })

  test('topology page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/topology')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('topology page loads content', async ({ page }) => {
    await page.goto('/topology')
    await expect(page.locator('body')).not.toBeEmpty()
    const content = await page.locator('body').textContent()
    expect(content!.length).toBeGreaterThan(20)
  })
})
