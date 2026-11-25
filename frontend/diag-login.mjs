import { chromium } from '@playwright/test'

const browser = await chromium.launch({
  executablePath: '/Users/mr.yang/Library/Caches/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-mac-arm64/chrome-headless-shell',
})
const page = await browser.newPage()

page.on('console', (msg) => console.log(`[console.${msg.type()}]`, msg.text()))
page.on('pageerror', (err) => console.log('[pageerror]', err.message))
page.on('response', (res) => {
  if (res.url().includes('/api/')) console.log('[api]', res.status(), res.url())
})

await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' })

// instrument the real DOM before interacting
await page.evaluate(() => {
  window.__events = []
  const form = document.querySelector('form')
  if (form) {
    form.addEventListener('submit', (e) => {
      window.__events.push('form-submit preventDefault=' + e.defaultPrevented)
    })
  }
  const btn = document.querySelector('button[type="submit"]')
  if (btn) {
    btn.addEventListener('click', () => window.__events.push('button-click'))
  }
})

await page.fill('input[placeholder*="手机号"]', '13800138000')
await page.fill('input[placeholder*="密码"]', 'password123')

console.log('disabled =', await page.locator('button[type="submit"]').isDisabled())

await page.locator('button[type="submit"]').click()
console.log('=== clicked ===')
await page.waitForTimeout(2500)

console.log('events =', JSON.stringify(await page.evaluate(() => window.__events)))
console.log('url =', page.url())
console.log('toast count =', await page.locator('.toast').count())

await browser.close()