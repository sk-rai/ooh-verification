import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Login & Dashboard', () => {
  test('should login and show dashboard', async ({ page }) => {
    await loginAsClient(page)
    await page.waitForTimeout(3000)
    await expect(page.locator('text=Welcome')).toBeVisible({ timeout: 10000 })
  })
})
