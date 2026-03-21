/**
 * Shared E2E test helpers for NeuraNAC Playwright specs.
 */
import { Page } from '@playwright/test'

/** Inject a fake auth token into localStorage so protected routes render. */
export async function injectAuth(page: Page) {
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.setItem(
      'neuranac-auth',
      JSON.stringify({
        state: {
          isAuthenticated: true,
          accessToken: 'fake-e2e-token',
          refreshToken: 'fake-refresh',
          user: {
            id: 'u1',
            username: 'admin',
            tenantId: 't1',
            roles: ['admin'],
          },
        },
        version: 0,
      })
    )
  })
}

/** Collect JS errors during page interaction, filtering expected API/network errors. */
export function collectCriticalErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (err) => {
    const msg = err.message
    // Ignore expected errors when no backend is running
    if (
      msg.includes('fetch') ||
      msg.includes('Network') ||
      msg.includes('401') ||
      msg.includes('Failed to fetch') ||
      msg.includes('ERR_CONNECTION_REFUSED') ||
      msg.includes('ECONNREFUSED') ||
      msg.includes('AbortError') ||
      msg.includes('TypeError: Load failed')
    ) {
      return
    }
    errors.push(msg)
  })
  return errors
}
