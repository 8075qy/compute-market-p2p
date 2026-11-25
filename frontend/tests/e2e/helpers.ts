import { Page, Locator, expect } from '@playwright/test';

export async function login(page: Page, phone: string, password: string) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.fill('input[placeholder*="手机号"]', phone);
  await page.fill('input[placeholder*="密码"]', password);
  await page.click('button:has-text("登录")');
  await page.waitForURL('**/home**');
  await page.waitForLoadState('networkidle');
}

export async function register(page: Page, phone: string, nickname: string, password: string, role: 'supplier' | 'demander') {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.click('text=注册');
  await page.fill('input[placeholder*="手机号"]', phone);
  await page.fill('input[placeholder*="昵称"]', nickname);
  await page.fill('input[placeholder*="密码"]', password);
  await page.click(`text=我是算力${role === 'supplier' ? '供给方' : '需求方'}`);
  await page.click('button:has-text("发送验证码")');
  await page.waitForTimeout(2000);
  await page.fill('input[placeholder*="验证码"]', '123456');
  await page.click('button:has-text("注册")');
  await page.waitForURL('**/home**');
  await page.waitForLoadState('networkidle');
}

export async function waitForToast(page: Page, message: string) {
  await expect(page.locator(`text=${message}`)).toBeVisible({ timeout: 10000 });
}

export async function clickAndWaitForNavigation(page: Page, selector: string, urlPattern: string) {
  await Promise.all([
    page.waitForURL(urlPattern),
    page.click(selector),
  ]);
}

export async function fillForm(page: Page, fields: Record<string, string>) {
  for (const [selector, value] of Object.entries(fields)) {
    await page.fill(selector, value);
  }
}

export async function selectOption(page: Page, selector: string, value: string) {
  await page.selectOption(selector, value);
}

export async function expectElementVisible(page: Page, selector: string) {
  await expect(page.locator(selector)).toBeVisible();
}

export async function expectElementNotVisible(page: Page, selector: string) {
  await expect(page.locator(selector)).not.toBeVisible();
}

export async function expectTextContent(page: Page, selector: string, text: string) {
  await expect(page.locator(selector)).toContainText(text);
}

export async function handleConfirmDialog(page: Page, accept: boolean = true) {
  page.on('dialog', async dialog => {
    if (accept) {
      await dialog.accept();
    } else {
      await dialog.dismiss();
    }
  });
}

export function generateRandomPhone(): string {
  return `13${Math.floor(Math.random() * 100000000).toString().padStart(8, '0')}`;
}

export function generateRandomNickname(): string {
  return `User_${Math.random().toString(36).substring(2, 8)}`;
}