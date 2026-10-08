/**
 * TrustCapture — Demo Capture Suite
 *
 * Produces an ordered set of clean, viewport-sized screenshots for stitching
 * into a product demo video (web). Numbered in capture order so ffmpeg can
 * assemble them directly.
 *
 * Flow:
 *   1. Landing page (scrolled slices)
 *   2. Registration (fill real form with a fresh demo account)
 *   3. Login as the demo account -> empty dashboard
 *   4. Create campaign (manual)
 *   5. Create vendor (manual)
 *   6. Bulk upload — campaigns, vendors, campaign-setup
 *   7. Switch to data-rich account (rai_sk) for Reports / Map / Tracking / Gallery
 *
 * Screens requiring real data use the existing rai_sk account.
 * New-account flows use DEMO_ACCOUNT (set to an UNUSED email).
 *
 * Run (from web/):   npx playwright test demo-capture.spec.ts
 * Output:            web/demo-shots/NN-description.png  (viewport 1920x1080)
 *
 * NOTE: Review CONFIG below before running. Registration creates a real account.
 */
import { test, expect, Page } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

// ─── CONFIG — EDIT BEFORE RUNNING ────────────────────────────────────────────
const CONFIG = {
  // Two unused mail IDs for registration demo. Set the real ones here.
  // Using a timestamp suffix avoids "email already registered" on re-runs;
  // remove the suffix if you want the exact address.
  demoAccount: {
    email: 'trustcapture@gmail.com',
    password: 'DemoPass@2026#',
    companyName: 'Demo Fieldworks Pvt Ltd',
    phone: '+919000000001',
    contactPerson: 'Demo Admin',
    designation: 'Operations Manager',
    city: 'Mumbai',
    website: 'https://demo-fieldworks.example.com',
  },
  // Data-rich account for Reports/Map/Tracking/Gallery screens.
  dataAccount: {
    email: 'rai_sk@yahoo.com',
    password: 'Poplu01@#',
  },
  outDir: 'demo-shots',
}
// ─────────────────────────────────────────────────────────────────────────────

const OUT = path.join(process.cwd(), CONFIG.outDir)
let shotIndex = 1

function ensureOutDir() {
  if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true })
}

/** Capture a single viewport-sized screenshot (NOT fullPage). */
async function shot(page: Page, name: string) {
  const num = String(shotIndex++).padStart(2, '0')
  const file = path.join(OUT, `${num}-${name}.png`)
  await page.waitForTimeout(600) // let any animation settle
  await page.screenshot({ path: file, fullPage: false })
  console.log(`  📸 ${num}-${name}.png`)
}

/**
 * Capture a tall page as multiple viewport slices by scrolling.
 * Produces NN-name-01, NN-name-02, ... so the video shows a scroll-through.
 */
async function scrollShots(page: Page, name: string, opts?: { maxSlices?: number; step?: number }) {
  const maxSlices = opts?.maxSlices ?? 6
  const viewportH = page.viewportSize()?.height ?? 1080
  const step = opts?.step ?? Math.floor(viewportH * 0.85) // overlap a little
  const totalH = await page.evaluate(() => document.body.scrollHeight)

  let y = 0
  let slice = 1
  while (slice <= maxSlices) {
    await page.evaluate((yy) => window.scrollTo({ top: yy, behavior: 'instant' as ScrollBehavior }), y)
    await page.waitForTimeout(500)
    const num = String(shotIndex).padStart(2, '0')
    const sliceLabel = String(slice).padStart(2, '0')
    const file = path.join(OUT, `${num}-${name}-${sliceLabel}.png`)
    await page.screenshot({ path: file, fullPage: false })
    console.log(`  📸 ${num}-${name}-${sliceLabel}.png`)
    y += step
    slice++
    if (y >= totalH) break
  }
  shotIndex++
  // reset scroll
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' as ScrollBehavior }))
}

async function login(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.waitForTimeout(500)
  await page.fill('input[type="email"]', email)
  await page.fill('input[type="password"]', password)
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard**', { timeout: 20000 })
}

test.describe('TrustCapture demo capture', () => {
  test.beforeAll(() => ensureOutDir())

  // 1920x1080 viewport for clean landscape frames
  test.use({ viewport: { width: 1920, height: 1080 } })

  test('full web journey capture', async ({ page }) => {
    test.setTimeout(300000) // 5 min — long walk-through

    // ── 1. LANDING PAGE (scroll slices) ──────────────────────────────────────
    await page.goto('/')
    await page.waitForTimeout(1500)
    await scrollShots(page, 'landing', { maxSlices: 8 })

    // ── 2. REGISTRATION FORM ─────────────────────────────────────────────────
    await page.goto('/register')
    await page.waitForTimeout(800)
    await shot(page, 'register-blank')

    // Fill the form (do NOT submit yet — capture filled state first)
    await page.fill('#email', CONFIG.demoAccount.email)
    await page.fill('#password', CONFIG.demoAccount.password)
    await page.fill('#contactPerson', CONFIG.demoAccount.contactPerson)
    await page.fill('#designation', CONFIG.demoAccount.designation)
    await page.fill('#companyName', CONFIG.demoAccount.companyName)
    await page.fill('#companyPhone', CONFIG.demoAccount.phone)
    // Country select (India) then city
    await page.selectOption('#country', { label: 'India' }).catch(() => {})
    await page.waitForTimeout(400)
    await page.fill('#city', CONFIG.demoAccount.city)
    await page.fill('#website', CONFIG.demoAccount.website)
    await page.selectOption('#industry', { label: 'Construction' }).catch(() => {})
    await scrollShots(page, 'register-filled', { maxSlices: 3 })

    // Submit — creates the demo account and lands on dashboard.
    // Comment out the next 3 lines if you do NOT want to actually register.
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard**', { timeout: 20000 }).catch(() => {})
    await shot(page, 'dashboard-new-account')

    // ── 4. CREATE CAMPAIGN (manual) ──────────────────────────────────────────
    await page.goto('/campaigns')
    await page.waitForTimeout(800)
    await shot(page, 'campaigns-list-empty')
    // open create form
    await page.goto('/campaigns/new').catch(() => {})
    await page.waitForTimeout(800)
    await scrollShots(page, 'campaign-create-form', { maxSlices: 4 })

    // ── 5. CREATE VENDOR (manual) ────────────────────────────────────────────
    await page.goto('/vendors')
    await page.waitForTimeout(800)
    await shot(page, 'vendors-list-empty')
    await page.goto('/vendors/new').catch(() => {})
    await page.waitForTimeout(800)
    await shot(page, 'vendor-create-form')

    // ── 7. DATA-RICH + PAID-TIER SCREENS (switch to rai_sk, Enterprise) ───────
    // Note: the fresh demo account is Free tier (bulk locked). rai_sk is Enterprise,
    // so the all-in-one Campaign Setup + bulk features are captured here.
    await page.goto('/login')
    // logout first if needed
    await page.evaluate(() => localStorage.removeItem('token')).catch(() => {})
    await login(page, CONFIG.dataAccount.email, CONFIG.dataAccount.password)
    await shot(page, 'dashboard-with-data')

    // ── 6. BULK — Campaign Setup (All-in-One) with LIVE upload + results ──────
    await page.goto('/campaigns')
    await page.waitForTimeout(800)
    // Open the new "Campaign Setup (All-in-One)" tab
    await page.getByText('Campaign Setup', { exact: false }).first().click().catch(() => {})
    await page.waitForTimeout(1000)
    await scrollShots(page, 'bulk-setup-intro', { maxSlices: 2 })

    // Attach the demo CSV to the hidden file input and upload it
    const csvPath = path.join(process.cwd(), 'tests', 'fixtures', 'demo_campaign_setup.csv')
    const fileInput = page.locator('input[type="file"]').first()
    if (await fileInput.count()) {
      await fileInput.setInputFiles(csvPath).catch((e) => console.log('setInputFiles failed:', e))
      await page.waitForTimeout(800)
      await shot(page, 'bulk-setup-file-selected')
      // Click Upload
      await page.getByRole('button', { name: /^Upload$/ }).first().click().catch(() => {})
      // Wait for results panel (geocoding can take a few seconds)
      await page.getByText('Upload Results', { exact: false }).first().waitFor({ timeout: 60000 }).catch(() => {})
      await page.waitForTimeout(1000)
      await scrollShots(page, 'bulk-setup-results', { maxSlices: 3 })
    } else {
      await shot(page, 'bulk-setup-no-input')
    }

    // Campaigns (with data)
    await page.goto('/campaigns'); await page.waitForTimeout(1000)
    await scrollShots(page, 'campaigns-list-data', { maxSlices: 3 })

    // Campaign detail (first campaign) incl. bulk assign sub-tab
    const firstCampaign = page.locator('a[href^="/campaigns/"]').first()
    if (await firstCampaign.count()) {
      await firstCampaign.click().catch(() => {})
      await page.waitForTimeout(1200)
      await scrollShots(page, 'campaign-detail', { maxSlices: 3 })
      await page.getByText('Bulk Assign', { exact: false }).first().click().catch(() => {})
      await page.waitForTimeout(800)
      await shot(page, 'bulk-assign-vendors')
    }

    // Vendors (with data)
    await page.goto('/vendors'); await page.waitForTimeout(1000)
    await scrollShots(page, 'vendors-list-data', { maxSlices: 4 })

    // Photos / evidence gallery
    await page.goto('/photos'); await page.waitForTimeout(1500)
    await scrollShots(page, 'evidence-gallery', { maxSlices: 6 })

    // Map
    await page.goto('/map'); await page.waitForTimeout(2000)
    await shot(page, 'map-view')

    // Tracking
    await page.goto('/tracking'); await page.waitForTimeout(2000)
    await scrollShots(page, 'tracking', { maxSlices: 2 })

    // Reports — Charts tab
    await page.goto('/reports'); await page.waitForTimeout(2000)
    await scrollShots(page, 'reports-charts', { maxSlices: 3 })
    // Reports — Report Data tab
    await page.getByText('View Report Data', { exact: false }).first().click().catch(() => {})
    await page.waitForTimeout(1200)
    await scrollShots(page, 'reports-table', { maxSlices: 4 })
    // Reports — Site Visits tab
    await page.getByText('Site Visits', { exact: false }).first().click().catch(() => {})
    await page.waitForTimeout(1200)
    await scrollShots(page, 'reports-site-visits', { maxSlices: 3 })

    // Subscription / pricing
    await page.goto('/subscription').catch(() => {})
    await page.waitForTimeout(1000)
    await scrollShots(page, 'subscription', { maxSlices: 3 })

    console.log(`\n✅ Capture complete. Shots in: ${OUT}`)
    expect(shotIndex).toBeGreaterThan(1)
  })
})
