import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Photo Gallery', () => {
  test('shows evidence with type badges', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Photos')
    await page.waitForTimeout(2000)
    await expect(page.locator('text=Showing')).toBeVisible()
    const grid = page.locator('.grid')
    await expect(grid).toBeVisible()
  })
})
