import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Photo Gallery', () => {
  test('shows evidence with all types', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Photos')
    await page.waitForTimeout(5000)
    await page.screenshot({ path: 'screenshots/02-photo-gallery.png', fullPage: true })
    // Try clicking first card
    const cards = page.locator('.grid button')
    if (await cards.count() > 0) {
      await cards.first().click()
      await page.waitForTimeout(1500)
      await page.screenshot({ path: 'screenshots/02-photo-detail-modal.png', fullPage: true })
    }
  })
})
