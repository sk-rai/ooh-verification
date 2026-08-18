import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Map View', () => {
  test('shows map with photo locations', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Map')
    // Wait for map to render with data
    await page.waitForTimeout(8000)
    await page.screenshot({ path: 'screenshots/04-map-view.png', fullPage: true })
  })
})
