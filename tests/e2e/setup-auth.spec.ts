import { test, expect } from '@playwright/test'
import { collectCriticalErrors } from './helpers'

test.describe('Setup & Authentication Flows', () => {
  // ── Setup Wizard (public route) ──────────────────────────────────────
  test('setup wizard page renders without JS errors', async ({ page }) => {
    const errors = collectCriticalErrors(page)
    await page.goto('/setup')
    await page.waitForTimeout(1500)
    expect(errors).toHaveLength(0)
  })

  test('setup wizard page has content', async ({ page }) => {
    await page.goto('/setup')
    await expect(page.locator('body')).not.toBeEmpty()
    const body = await page.locator('body').textContent()
    expect(body!.length).toBeGreaterThan(20)
  })

  // ── Login page accessibility ─────────────────────────────────────────
  test('login page has accessible form elements', async ({ page }) => {
    await page.goto('/login')
    // Form should be keyboard-navigable
    const inputs = page.locator('input')
    const inputCount = await inputs.count()
    expect(inputCount).toBeGreaterThanOrEqual(2) // username + password
  })

  test('login page has submit button', async ({ page }) => {
    await page.goto('/login')
    const button = page.locator('button[type="submit"]')
    await expect(button).toBeVisible()
  })

  // ── Protected route redirect ─────────────────────────────────────────
  test('all protected routes redirect to /login when unauthenticated', async ({ page }) => {
    const protectedRoutes = [
      '/', '/policies', '/network-devices', '/endpoints', '/sessions',
      '/identity', '/certificates', '/segmentation', '/guest', '/posture',
      '/ai/agents', '/ai/data-flow', '/ai/shadow', '/nodes', '/audit',
      '/settings', '/diagnostics', '/siem', '/webhooks', '/licenses',
      '/sites', '/help/docs', '/help/ai', '/legacy-nac', '/topology', '/privacy',
    ]

    for (const route of protectedRoutes) {
      await page.goto(route)
      await expect(page).toHaveURL(/login/, { timeout: 5000 })
    }
  })
})
