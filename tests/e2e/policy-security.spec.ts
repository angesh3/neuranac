import { test, expect } from '@playwright/test'
import { injectAuth, collectCriticalErrors } from './helpers'

test.describe('Policy & Security Pages', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  // ── Policies ─────────────────────────────────────────────────────────
  test('policies page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/policies')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('policies page has heading', async ({ page }) => {
    await page.goto('/policies')
    const body = await page.locator('body').textContent()
    expect(body!.toLowerCase()).toContain('polic')
  })

  // ── Segmentation ─────────────────────────────────────────────────────
  test('segmentation page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/segmentation')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('segmentation page loads content', async ({ page }) => {
    await page.goto('/segmentation')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Posture ──────────────────────────────────────────────────────────
  test('posture page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/posture')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('posture page loads content', async ({ page }) => {
    await page.goto('/posture')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Certificates ─────────────────────────────────────────────────────
  test('certificates page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/certificates')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('certificates page loads content', async ({ page }) => {
    await page.goto('/certificates')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Privacy ──────────────────────────────────────────────────────────
  test('privacy page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/privacy')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('privacy page loads content', async ({ page }) => {
    await page.goto('/privacy')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })
})
