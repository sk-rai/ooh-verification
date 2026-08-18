import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Reports', () => {
  test('shows statistics and all tabs', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Reports')
    await page.waitForTimeout(5000)
    await page.screenshot({ path: 'screenshots/03-reports-charts.png', fullPage: true })
    const reportDataBtn = page.locator('text=View Report Data')
    if (await reportDataBtn.isVisible()) {
      await reportDataBtn.click()
      await page.waitForTimeout(3000)
      await page.screenshot({ path: 'screenshots/03-reports-table.png', fullPage: true })
    }
    const siteVisitsBtn = page.locator('text=Site Visits')
    if (await siteVisitsBtn.isVisible()) {
      await siteVisitsBtn.click()
      await page.waitForTimeout(3000)
      await page.screenshot({ path: 'screenshots/03-reports-site-visits.png', fullPage: true })
    }
  })
})
