import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Tracking', () => {
  test('tracking page with map and attendance log', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Tracking')
    await page.waitForSelector('text=GPS Tracking', { timeout: 10000 })
    await page.waitForTimeout(3000)
    await page.screenshot({ path: 'screenshots/05-tracking.png', fullPage: true })
  })
})
