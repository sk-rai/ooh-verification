import { test, expect } from '@playwright/test'

const API = 'https://api.trustcaptures.com'

test.describe('Bulk Upload & Campaign Setup', () => {
  let token: string

  test.beforeAll(async ({ request }) => {
    const res = await request.post(API + '/api/auth/login', {
      data: { email: 'rai_sk@yahoo.com', password: 'Poplu01@#' }
    })
    token = (await res.json()).access_token
  })

  test('download campaigns template', async ({ request }) => {
    const res = await request.get(API + '/api/bulk/campaigns/template', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const text = await res.text()
    expect(text).toContain('name,campaign_type,start_date,end_date')
  })

  test('download vendors template', async ({ request }) => {
    const res = await request.get(API + '/api/bulk/vendors/template', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const text = await res.text()
    expect(text).toContain('name,phone_number')
  })

  test('download assignments template', async ({ request }) => {
    const res = await request.get(API + '/api/bulk/assignments/template', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const text = await res.text()
    expect(text).toContain('campaign_code,vendor_id')
  })

  test('download campaign-setup template', async ({ request }) => {
    const res = await request.get(API + '/api/bulk/campaign-setup/template', {
      headers: { Authorization: 'Bearer ' + token }
    })
    expect(res.status()).toBe(200)
    const text = await res.text()
    expect(text).toContain('campaign_name,campaign_type,start_date,end_date,location_address,vendor_name,vendor_phone')
  })

  test('bulk upload vendors via CSV', async ({ request }) => {
    const csv = 'name,phone_number,email\n"PW Test Vendor","+919000099001","pwtest@test.com"\n'
    const res = await request.post(API + '/api/bulk/vendors', {
      headers: { Authorization: 'Bearer ' + token },
      multipart: {
        file: { name: 'vendors.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) }
      }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.total_rows).toBe(1)
    expect(data.successful + data.failed).toBe(1)
  })

  test('bulk campaign-setup creates campaign + vendor + assignment', async ({ request }) => {
    const csv = 'campaign_name,campaign_type,start_date,end_date,location_address,vendor_name,vendor_phone,vendor_email\n"PW Bulk Test Camp","ooh","2026-09-01","2026-09-30","Connaught Place, Delhi","PW Bulk Vendor","+919000099002",""\n'
    const res = await request.post(API + '/api/bulk/campaign-setup', {
      headers: { Authorization: 'Bearer ' + token },
      multipart: {
        file: { name: 'setup.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) }
      }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.total_rows).toBe(1)
    expect(data.successful).toBe(1)
    expect(data.results[0].data.campaign).toBe('PW Bulk Test Camp')
    expect(data.results[0].data.vendor_phone).toBe('+919000099002')
  })

  test('bulk assignment with invalid vendor fails gracefully', async ({ request }) => {
    const csv = 'campaign_code,vendor_id,address,latitude,longitude,location_name\n"INVALID-CODE","XXXXXX","Test Address",,,\n'
    const res = await request.post(API + '/api/bulk/assignments', {
      headers: { Authorization: 'Bearer ' + token },
      multipart: {
        file: { name: 'assignments.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) }
      }
    })
    expect(res.status()).toBe(200)
    const data = await res.json()
    expect(data.failed).toBe(1)
    expect(data.results[0].status).toBe('error')
  })
})
