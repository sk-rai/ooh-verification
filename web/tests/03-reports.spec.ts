import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Reports', () => {
  test('shows statistics and site visits tab', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Reports')
    await page.waitForTimeout(5000)
    await expect(page.locator('text=Verified')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('text=Site Visits')).toBeVisible({ timeout: 5000 })
  })
})
