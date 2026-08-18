import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Campaign Creation', () => {
  test('shows capture settings config section', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Campaigns')
    await page.waitForTimeout(2000)
    // Find and click create button
    const createLink = page.locator('a[href*="create"], a[href*="new"], button:has-text("Create")')
    await createLink.first().click()
    await page.waitForTimeout(3000)
    await expect(page.locator('text=Capture Settings')).toBeVisible({ timeout: 10000 })
  })
})
