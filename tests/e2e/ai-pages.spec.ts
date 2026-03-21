import { test, expect } from '@playwright/test'
import { injectAuth, collectCriticalErrors } from './helpers'

test.describe('AI Feature Pages', () => {
  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  // ── AI Agents ────────────────────────────────────────────────────────
  test('AI agents page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/ai/agents')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('AI agents page has content', async ({ page }) => {
    await page.goto('/ai/agents')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── AI Data Flow ─────────────────────────────────────────────────────
  test('AI data flow page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/ai/data-flow')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('AI data flow page has content', async ({ page }) => {
    await page.goto('/ai/data-flow')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  // ── Shadow AI ────────────────────────────────────────────────────────
  test('Shadow AI page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/ai/shadow')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('Shadow AI page has content', async ({ page }) => {
    await page.goto('/ai/shadow')
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── AI Help / Assistant ──────────────────────────────────────────────
  test('AI assistant page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/help/ai')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('AI assistant page has content', async ({ page }) => {
    await page.goto('/help/ai')
    await expect(page.locator('body')).not.toBeEmpty()
  })
})
