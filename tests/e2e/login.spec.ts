import { test, expect } from '@playwright/test'

test.describe('Login Page', () => {
  test('shows login form', async ({ page }) => {
    await page.goto('/login')
    // The login page should have username and password fields
    await expect(page.locator('input[type="text"], input[name="username"]')).toBeVisible()
    await expect(page.locator('input[type="password"]')).toBeVisible()
  })

  test('rejects invalid credentials', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="text"], input[name="username"]', 'baduser')
    await page.fill('input[type="password"]', 'badpass')
    await page.click('button[type="submit"]')
    // Should show error or stay on login page
    await expect(page).toHaveURL(/login/)
  })

  test('redirects unauthenticated users to login', async ({ page }) => {
    await page.goto('/policies')
    // Should redirect to login for protected routes
    await expect(page).toHaveURL(/login/)
  })
})
