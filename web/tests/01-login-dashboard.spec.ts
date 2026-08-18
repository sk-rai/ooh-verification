import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Login & Dashboard', () => {
  test('should login and show dashboard with data', async ({ page }) => {
    await loginAsClient(page)
    await page.waitForTimeout(5000)
    await page.screenshot({ path: 'screenshots/01-dashboard.png', fullPage: true })
  })
})
