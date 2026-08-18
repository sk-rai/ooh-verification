import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Map View', () => {
  test('shows map page', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Map')
    await page.waitForTimeout(8000)
    const hasMap = await page.locator('.leaflet-container').isVisible().catch(() => false)
    const hasText = await page.locator('text=Map View').isVisible().catch(() => false)
    expect(hasMap || hasText).toBeTruthy()
  })
})
