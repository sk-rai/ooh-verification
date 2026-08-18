import { test, expect } from '@playwright/test'
import { loginAsClient } from './auth.setup'

test.describe('Vendors', () => {
  test('shows vendor list', async ({ page }) => {
    await loginAsClient(page)
    await page.click('text=Vendors')
    await page.waitForTimeout(3000)
    await page.screenshot({ path: 'screenshots/08-vendors-list.png', fullPage: true })
  })
})
