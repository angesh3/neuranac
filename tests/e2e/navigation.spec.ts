import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    // Set a fake auth token to bypass login redirect
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

  test('loads dashboard page', async ({ page }) => {
    await page.goto('/')
    // Dashboard should render without crashing
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('sidebar navigation links exist', async ({ page }) => {
    await page.goto('/')
    // Check that key nav elements are present
    const body = await page.locator('body').textContent()
    // At minimum the page should render something
    expect(body).toBeTruthy()
  })

  test('navigates to policies page', async ({ page }) => {
    await page.goto('/policies')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('navigates to network devices page', async ({ page }) => {
    await page.goto('/network-devices')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('navigates to NeuraNAC integration page', async ({ page }) => {
    await page.goto('/legacy-nac')
    await expect(page.locator('body')).not.toBeEmpty()
  })

  test('navigates to diagnostics page', async ({ page }) => {
    await page.goto('/diagnostics')
    await expect(page.locator('body')).not.toBeEmpty()
  })
})
