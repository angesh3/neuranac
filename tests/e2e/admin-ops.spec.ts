import { test, expect } from '@playwright/test'
import { injectAuth, collectCriticalErrors } from './helpers'

test.describe('Administration & Operations Pages', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  // ── Site Management ──────────────────────────────────────────────────
  test('site management page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/sites')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('site management page has content', async ({ page }) => {
    await page.goto('/sites')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── On-Prem Setup Wizard ─────────────────────────────────────────────
  test('on-prem setup wizard renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/sites/onprem-setup')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  // ── Twin Nodes ───────────────────────────────────────────────────────
  test('nodes page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/nodes')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('nodes page has content', async ({ page }) => {
    await page.goto('/nodes')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── SIEM ─────────────────────────────────────────────────────────────
  test('SIEM page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/siem')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('SIEM page has content', async ({ page }) => {
    await page.goto('/siem')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Webhooks ─────────────────────────────────────────────────────────
  test('webhooks page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/webhooks')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('webhooks page has content', async ({ page }) => {
    await page.goto('/webhooks')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Licenses ─────────────────────────────────────────────────────────
  test('licenses page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/licenses')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('licenses page has content', async ({ page }) => {
    await page.goto('/licenses')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Audit Log ────────────────────────────────────────────────────────
  test('audit page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/audit')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('audit page has content', async ({ page }) => {
    await page.goto('/audit')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Diagnostics ──────────────────────────────────────────────────────
  test('diagnostics page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/diagnostics')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('diagnostics page has content', async ({ page }) => {
    await page.goto('/diagnostics')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Settings ─────────────────────────────────────────────────────────
  test('settings page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/settings')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('settings page has content', async ({ page }) => {
    await page.goto('/settings')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Help Docs ────────────────────────────────────────────────────────
  test('help docs page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/help/docs')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('help docs page has content', async ({ page }) => {
    await page.goto('/help/docs')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })
})
