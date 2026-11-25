import { test, expect } from '@playwright/test';

test.describe('Settings Page', () => {
  test.use({ storageState: 'tests/e2e/.auth/user.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
  });

  test('should display settings page', async ({ page }) => {
    await expect(page.locator('text=设置')).toBeVisible();
    await expect(page.locator('.tabbar')).toBeVisible();
  });

  test('should show profile card', async ({ page }) => {
    await expect(page.locator('text=账户信息')).toBeVisible();
    await expect(page.locator('.profile-avatar')).toBeVisible();
    await expect(page.locator('.profile-nickname')).toBeVisible();
    await expect(page.locator('.profile-role-badge')).toBeVisible();
  });

  test('should show edit profile button', async ({ page }) => {
    await expect(page.locator('button:has-text("编辑资料")')).toBeVisible();
  });

  test('should open edit profile modal', async ({ page }) => {
    await page.click('button:has-text("编辑资料")');
    await expect(page.locator('text=编辑资料')).toBeVisible();
    await expect(page.locator('input[placeholder*="昵称"]')).toBeVisible();
    await expect(page.locator('input[placeholder*="手机号"]')).toBeVisible();
  });

  test('should update nickname', async ({ page }) => {
    await page.click('button:has-text("编辑资料")');
    await page.fill('input[placeholder*="昵称"]', 'Updated Nickname');
    await page.click('button:has-text("保存")');
    await expect(page.locator('text=保存成功')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.profile-nickname')).toContainText('Updated Nickname');
  });

  test('should show balance grid', async ({ page }) => {
    await expect(page.locator('text=可用余额')).toBeVisible();
    await expect(page.locator('text=冻结余额')).toBeVisible();
    await expect(page.locator('text=累计收入')).toBeVisible();
    await expect(page.locator('text=累计支出')).toBeVisible();
  });

  test('should show withdrawal account section', async ({ page }) => {
    await expect(page.locator('text=提现账户')).toBeVisible();
  });

  test('should bind withdrawal account', async ({ page }) => {
    const bindButton = page.locator('button:has-text("绑定提现账户")').first();
    if (await bindButton.isVisible()) {
      await bindButton.click();
      await expect(page.locator('text=绑定提现账户')).toBeVisible();
      await expect(page.locator('text=支付宝')).toBeVisible();
      await expect(page.locator('text=微信')).toBeVisible();
      await expect(page.locator('text=银行卡')).toBeVisible();
    }
  });

  test('should select Alipay and fill form', async ({ page }) => {
    const bindButton = page.locator('button:has-text("绑定提现账户")').first();
    if (await bindButton.isVisible()) {
      await bindButton.click();
      await page.click('text=支付宝');
      await expect(page.locator('input[placeholder*="支付宝账号"]')).toBeVisible();
      await expect(page.locator('input[placeholder*="真实姓名"]')).toBeVisible();
      await page.fill('input[placeholder*="支付宝账号"]', 'test@alipay.com');
      await page.fill('input[placeholder*="真实姓名"]', 'Test User');
      await page.click('button:has-text("下一步")');
      await expect(page.locator('text=验证码')).toBeVisible();
    }
  });

  test('should send verification code for withdrawal bind', async ({ page }) => {
    const bindButton = page.locator('button:has-text("绑定提现账户")').first();
    if (await bindButton.isVisible()) {
      await bindButton.click();
      await page.click('text=微信');
      await page.fill('input[placeholder*="微信号"]', 'test_wechat');
      await page.fill('input[placeholder*="真实姓名"]', 'Test User');
      await page.click('button:has-text("下一步")');
      await page.click('button:has-text("发送验证码")');
      await expect(page.locator('text=验证码已发送')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should verify 6-digit code', async ({ page }) => {
    const bindButton = page.locator('button:has-text("绑定提现账户")').first();
    if (await bindButton.isVisible()) {
      await bindButton.click();
      await page.click('text=银行卡');
      await page.fill('input[placeholder*="银行卡号"]', '6222000000000000000');
      await page.fill('input[placeholder*="开户行"]', '中国工商银行');
      await page.fill('input[placeholder*="真实姓名"]', 'Test User');
      await page.click('button:has-text("下一步")');
      await page.fill('input[placeholder*="验证码"]', '123456');
      await page.click('button:has-text("确定")');
      await expect(page.locator('text=绑定成功')).toBeVisible({ timeout: 5000 });
    }
  });

  test('should show about section', async ({ page }) => {
    await expect(page.locator('text=关于')).toBeVisible();
    await expect(page.locator('text=版本')).toBeVisible();
    await expect(page.locator('text=用户协议')).toBeVisible();
    await expect(page.locator('text=隐私政策')).toBeVisible();
  });

  test('should show logout button', async ({ page }) => {
    await expect(page.locator('button:has-text("退出登录")')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    await page.click('button:has-text("退出登录")');
    await expect(page.locator('text=确定要退出登录吗')).toBeVisible();
    await page.click('button:has-text("确定")');
    await page.waitForURL('**/login**');
    await expect(page.locator('text=登录')).toBeVisible();
  });

  test('should show amounts with tabular-nums in balance grid', async ({ page }) => {
    const balanceElements = page.locator('.balance-grid .tabular-nums');
    await expect(balanceElements.first()).toHaveCSS('font-variant-numeric', 'tabular-nums');
  });
});