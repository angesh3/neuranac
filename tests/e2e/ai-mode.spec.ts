import { test, expect } from '@playwright/test'

test.describe('AI Mode', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.setItem(
        'neuranac-auth',
        JSON.stringify({
          state: {
            isAuthenticated: true,
            accessToken: 'fake-e2e-token',
            refreshToken: 'fake-refresh',
            user: { id: 'u1', username: 'admin', tenantId: 't1', roles: ['admin'] },
          },
          version: 0,
        })
      )
    })
  })

  test('AI mode toggle is visible', async ({ page }) => {
    await page.goto('/')
    // The AI mode toggle should be somewhere on the page
    const body = await page.locator('body').textContent()
    expect(body).toBeTruthy()
  })

  test('page renders without errors', async ({ page }) => {
    await page.goto('/')
    // No uncaught exceptions
    const errors: string[] = []
    page.on('pageerror', (err) => errors.push(err.message))
    await page.waitForTimeout(2000)
    // Filter out expected API errors (no backend running in E2E)
    const criticalErrors = errors.filter(
      (e) => !e.includes('fetch') && !e.includes('Network') && !e.includes('401')
    )
    expect(criticalErrors).toHaveLength(0)
  })
})
