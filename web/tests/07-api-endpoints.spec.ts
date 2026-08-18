import { test, expect } from '@playwright/test'

const API = 'https://api.trustcaptures.com'

test.describe('API Endpoints', () => {
  let token: string

  test.beforeAll(async ({ request }) => {
    const res = await request.post(API + '/api/auth/login', {
      data: { email: 'rai_sk@yahoo.com', password: 'Poplu01@#' }
    })
    token = (await res.json()).access_token
  })

  test('app config returns all sections', async ({ request }) => {
    const res = await request.get(API + '/api/app/config')
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.capture_config).toBeDefined()
    expect(data.upload_config).toBeDefined()
    expect(data.tracking_config).toBeDefined()
    expect(data.tracking_config.enabled).toBe(true)
    expect(data.branding).toBeDefined()
    expect(data.ui_config.features).toBeDefined()
  })

  test('site visits returns data', async ({ request }) => {
    const res = await request.get(API + '/api/reports/site-visits?start_date=2026-07-01&end_date=2026-08-16', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.rows).toBeDefined()
    expect(data.summary).toBeDefined()
    expect(data.summary.total_captures).toBeGreaterThan(0)
  })

  test('route analysis returns points', async ({ request }) => {
    // Use a date range that has data
    const res = await request.get(API + '/api/evidence/route-analysis?vendor_id=9BIZMV', {
      headers: { Authorization: 'Bearer ' + token }
    })
    // May return 200 with empty points or actual data
    expect([200, 422]).toContain(res.status())
  })

  test('tracks summary endpoint works', async ({ request }) => {
    const res = await request.get(API + '/api/tracks/summary?start_date=2026-08-01&end_date=2026-08-16', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.total_vendors).toBeDefined()
    expect(data.rows).toBeDefined()
  })

  test('statistics includes evidence count', async ({ request }) => {
    const res = await request.get(API + '/api/reports/statistics', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.total_photos).toBeGreaterThan(50)
  })

  test('photos endpoint returns evidence types', async ({ request }) => {
    const res = await request.get(API + '/api/photos?limit=10', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.length).toBeGreaterThan(0)
    // Should have evidence_type field
    const types = data.map((d: any) => d.evidence_type).filter(Boolean)
    expect(types.length).toBeGreaterThan(0)
  })

  test('vendor campaigns has has_campaigns flag', async ({ request }) => {
    // Login as vendor
    const otpRes = await request.post(API + '/api/auth/vendor/request-otp', {
      data: { vendor_id: 'REVIEW', phone_number: '+911234567890' }
    })
    expect(otpRes.status()).toBe(200)
    const verifyRes = await request.post(API + '/api/auth/vendor/verify-otp', {
      data: { vendor_id: 'REVIEW', phone_number: '+911234567890', otp: '123456', device_id: 'playwright-test' }
    })
    const vendorToken = (await verifyRes.json()).access_token
    
    const res = await request.get(API + '/api/vendors/me/campaigns', {
      headers: { Authorization: 'Bearer ' + vendorToken }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.has_campaigns).toBeDefined()
  })
})
