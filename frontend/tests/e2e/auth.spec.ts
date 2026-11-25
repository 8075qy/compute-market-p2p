import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
  });

  test('should display login form', async ({ page }) => {
    await expect(page.locator('text=登录')).toBeVisible();
    await expect(page.locator('input[placeholder*="手机号"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="密码"]')).toBeVisible();
    await expect(page.locator('button:has-text("登录")')).toBeVisible();
  });

  test('should switch to register tab', async ({ page }) => {
    await page.click('text=注册');
    await expect(page.locator('text=注册账号')).toBeVisible();
    await expect(page.locator('input[placeholder*="昵称"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="验证码"]')).toBeVisible();
  });

  test('should validate phone number format', async ({ page }) => {
    await page.fill('input[placeholder*="手机号"]', '123');
    await page.fill('input[placeholder*="密码"]', 'password123');
    await page.click('button:has-text("登录")');
    await expect(page.locator('text=手机号格式不正确')).toBeVisible();
  });

  test('should validate password length', async ({ page }) => {
    await page.fill('input[placeholder*="手机号"]', '13800138000');
    await page.fill('input[placeholder*="密码"]', '123');
    await page.click('button:has-text("登录")');
    await expect(page.locator('text=密码长度')).toBeVisible();
  });

  test('should send verification code on register', async ({ page }) => {
    await page.click('text=注册');
    await page.fill('input[placeholder*="手机号"]', '13900139000');
    await page.fill('input[placeholder*="昵称"]', 'Test User');
    await page.click('button:has-text("发送验证码")');
    await expect(page.locator('text=验证码已发送')).toBeVisible({ timeout: 5000 });
  });

  test('should show role selection on register', async ({ page }) => {
    await page.click('text=注册');
    await expect(page.locator('text=我是算力供给方')).toBeVisible();
    await expect(page.locator('text=我是算力需求方')).toBeVisible();
  });
});

test.describe('Logged in state', () => {
  test.use({ storageState: 'tests/e2e/.auth/user.json' });

  test('should redirect to home after login', async ({ page }) => {
    await page.goto('/login');
    await page.waitForURL('**/home');
    await expect(page.locator('text=算力市场')).toBeVisible();
  });

  test('should show user profile in settings', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('text=账户设置')).toBeVisible();
  });
});