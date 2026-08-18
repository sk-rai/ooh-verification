import { Page } from '@playwright/test'

export const TEST_CLIENT = {
  email: 'rai_sk@yahoo.com',
  password: 'Poplu01@#',
}

export async function loginAsClient(page: Page) {
  await page.goto('/login')
  await page.fill('input[type="email"]', TEST_CLIENT.email)
  await page.fill('input[type="password"]', TEST_CLIENT.password)
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard**', { timeout: 15000 })
}
