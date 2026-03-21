import { test, expect } from '@playwright/test'
import { injectAuth, collectCriticalErrors } from './helpers'

test.describe('Network & Endpoint Pages', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  // ── Network Devices ──────────────────────────────────────────────────
  test('network devices page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/network-devices')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('network devices page has content', async ({ page }) => {
    await page.goto('/network-devices')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Endpoints ────────────────────────────────────────────────────────
  test('endpoints page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/endpoints')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('endpoints page has content', async ({ page }) => {
    await page.goto('/endpoints')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Sessions ─────────────────────────────────────────────────────────
  test('sessions page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/sessions')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('sessions page has content', async ({ page }) => {
    await page.goto('/sessions')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Identity Sources ─────────────────────────────────────────────────
  test('identity page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/identity')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('identity page has content', async ({ page }) => {
    await page.goto('/identity')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Guest & BYOD ────────────────────────────────────────────────────
  test('guest page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/guest')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('guest page has content', async ({ page }) => {
    await page.goto('/guest')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })
})
