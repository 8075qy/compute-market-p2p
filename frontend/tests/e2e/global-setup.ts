import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto('http://localhost:5173/login');
  await page.waitForLoadState('networkidle');

  await page.fill('input[placeholder*="手机号"]', '13800138000');
  await page.fill('input[placeholder*="密码"]', 'password123');
  await page.click('button:has-text("登录")');
  await page.waitForURL('**/home**');
  await page.waitForLoadState('networkidle');

  await page.context().storageState({ path: 'tests/e2e/.auth/user.json' });
  await browser.close();

  const browser2 = await chromium.launch();
  const page2 = await browser2.newPage();
  await page2.goto('http://localhost:5173/login');
  await page2.waitForLoadState('networkidle');

  await page2.click('text=注册');
  await page2.fill('input[placeholder*="手机号"]', '13900139000');
  await page2.fill('input[placeholder*="昵称"]', 'Test Supplier');
  await page2.fill('input[placeholder*="密码"]', 'password123');
  await page2.click('text=我是算力供给方');
  await page2.click('button:has-text("发送验证码")');
  await page2.waitForTimeout(2000);
  await page2.fill('input[placeholder*="验证码"]', '123456');
  await page2.click('button:has-text("注册")');
  await page2.waitForURL('**/home**');
  await page2.waitForLoadState('networkidle');

  await page2.context().storageState({ path: 'tests/e2e/.auth/supplier.json' });
  await browser2.close();

  const browser3 = await chromium.launch();
  const page3 = await browser3.newPage();
  await page3.goto('http://localhost:5173/login');
  await page3.waitForLoadState('networkidle');

  await page3.click('text=注册');
  await page3.fill('input[placeholder*="手机号"]', '13700137000');
  await page3.fill('input[placeholder*="昵称"]', 'Test Demander');
  await page3.fill('input[placeholder*="密码"]', 'password123');
  await page3.click('text=我是算力需求方');
  await page3.click('button:has-text("发送验证码")');
  await page3.waitForTimeout(2000);
  await page3.fill('input[placeholder*="验证码"]', '123456');
  await page3.click('button:has-text("注册")');
  await page3.waitForURL('**/home**');
  await page3.waitForLoadState('networkidle');

  await page3.context().storageState({ path: 'tests/e2e/.auth/demander.json' });
  await browser3.close();
}

export default globalSetup;