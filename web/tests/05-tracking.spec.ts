import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Tracking', () => {
  test('tracking page loads', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Tracking')
    await page.waitForTimeout(2000)
    await expect(page.locator('text=GPS Tracking')).toBeVisible()
    await expect(page.locator('text=Attendance Log')).toBeVisible()
  })
})
