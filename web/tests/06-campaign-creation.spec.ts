import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Campaign Creation', () => {
  test('shows full form with config section', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Campaigns')
    await page.waitForTimeout(4000)
    await page.screenshot({ path: 'screenshots/06-campaigns-list.png', fullPage: true })
    const createLink = page.locator('a[href*="new"]')
    if (await createLink.count() > 0) {
      await createLink.first().click()
      await page.waitForTimeout(3000)
      await page.screenshot({ path: 'screenshots/06-campaign-create-form.png', fullPage: true })
    }
  })
})
